import httpx
import time
import json
import asyncio
from database import get_memories, add_memory

# Configuration
OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b" # Default model, can be changed

class AIEngine:
    def __init__(self):
        self.history = []
        self.last_interaction_time = 0
        self.conversation_active = False

    async def chat(self, user_input: str, test_mode: bool = False):
        current_time = time.time()
        
        # Session Management: Reset if > 5 mins or "ありがとう" in PREVIOUS turn (logic handled at end of turn usually, but here checking start)
        # Requirement: "Last input > 5 mins or 'arigato' typed -> disregard previous messages"
        if (current_time - self.last_interaction_time > 300):
            self.history = []
            self.conversation_active = False
        
        self.last_interaction_time = current_time
        
        # 1. Retrieve Context
        # Using direct DB access as allowed by requirements for simplicity
        memories = get_memories()
        
        # format context
        attributes = []
        goals = []
        memory_list = []
        requests = []
        
        for m in memories:
            if m['category'] == 'attribute':
                attributes.append(m['content'])
            elif m['category'] == 'goal':
                goals.append(m['content'])
            elif m['category'] == 'request':
                requests.append(m['content'])
            else:
                memory_list.append(m['content'])

        # Minimizing context: Maybe limit number of items? 
        # For now, we include all. To optimize, we could only include recent ones or use keyword matching (future improvement).
        
        system_prompt = f"""
あなたは優秀なAI秘書です。
ユーザーの入力に対して、以下の情報を踏まえて適切に応答してください。
自然な日本語で答えてください。

[ユーザーの属性]
{json.dumps(attributes, ensure_ascii=False)}

[ユーザーの目標]
{json.dumps(goals, ensure_ascii=False)}

[アシスタントへのお願い]
{json.dumps(requests, ensure_ascii=False)}

[その他の記憶]
{json.dumps(memory_list, ensure_ascii=False)}
"""

        messages = [{"role": "system", "content": system_prompt}] + self.history + [{"role": "user", "content": user_input}]
        
        # 2. Call Ollama
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(OLLAMA_API_URL, json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": False
                }, timeout=60.0)
                
                if response.status_code != 200:
                    result_text = f"エラーが発生しました: {response.text}"
                else:
                    data = response.json()
                    result_text = data.get("message", {}).get("content", "")

        except Exception as e:
            result_text = f"通信エラー: {str(e)}"

        # 3. Update History
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": result_text})
        
        # Handle "Arigato" - Clear history for NEXT turn (or effectively end session)
        if "ありがとう" in user_input:
            self.history = [] # Reset explicitly
            self.conversation_active = False
        else:
            self.conversation_active = True

        # 4. Background Task: Analyze and Save (Fire and forget)
        asyncio.create_task(self.analyze_and_save(user_input, result_text))
        
        return {
            "response": result_text,
            "context_used": system_prompt if test_mode else None
        }

    async def analyze_and_save(self, user_text, assistant_text):
        prompt = f"""
以下のユーザーとAIの会話から、長期的に保存すべきユーザーの情報（属性、目標、記憶、アシスタントへの要望）を抽出してください。
保存すべき情報がない場合は、"items": [] としてください。
JSON形式のみで出力してください。Markdownのコードブロックは不要です。

フォーマット:
{{
    "items": [
        {{ "category": "attribute", "content": "ユーザーはプログラマーである" }},
        {{ "category": "goal", "content": "ユーザーはPythonをマスターしたい" }},
        {{ "category": "request", "content": "返答は短くしてほしい" }}
    ]
}}

有効なカテゴリ: attribute (属性), goal (目標), memory (一般記憶), request (要望)

[会話]
User: {user_text}
AI: {assistant_text}
"""
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(OLLAMA_API_URL, json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "format": "json",
                    "stream": False
                }, timeout=60.0)
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("message", {}).get("content", "")
                    try:
                        parsed = json.loads(content)
                        if "items" in parsed and isinstance(parsed["items"], list):
                            for item in parsed["items"]:
                                category = item.get("category")
                                content_str = item.get("content")
                                if category and content_str:
                                    # Basic validation
                                    if category in ['attribute', 'goal', 'memory', 'request']:
                                        add_memory(category, content_str)
                    except json.JSONDecodeError:
                        print("Failed to parse JSON from analysis")
        except Exception as e:
            print(f"Analysis failed: {e}")

