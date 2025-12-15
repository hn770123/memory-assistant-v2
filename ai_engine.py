# httpx: 非同期HTTPリクエストを行うためのライブラリ。AI APIへの通信に使用します。
import httpx
import time
import json
import asyncio
from database import get_memories, add_memory

# 設定
# ローカルで動作しているOllamaのAPIエンドポイント
OLLAMA_API_URL = "http://localhost:11434/api/chat"
# 使用するLLMのモデル名。Ollamaでpullしたモデルと一致させる必要があります。
MODEL_NAME = "llama3.1:8b" # ユーザー指定のモデル

class AIEngine:
    def __init__(self):
        # 会話履歴を保持するリスト。短期記憶として機能します。
        self.history = []
        # 最後にインタラクション（会話）があった時刻を記録します。
        self.last_interaction_time = 0
        self.conversation_active = False

    # AIとのチャットを行うメインのメソッド
    # async キーワードにより、この関数は非同期関数となり、awaitで実行待ちができます。
    async def chat(self, user_input: str, test_mode: bool = False):
        current_time = time.time()
        
        # セッション管理: コンテキストのリセット判定
        # 「最後の会話から5分経過」している場合、過去の履歴（短期記憶）を忘れます。
        # 人間同様、しばらく時間が経つと直前の話題を忘れる挙動を模倣しています。
        if (current_time - self.last_interaction_time > 300):
            self.history = []
            self.conversation_active = False
        
        self.last_interaction_time = current_time
        
        # 1. コンテキスト（長期記憶）の取得
        # データベースから過去の記憶を取得し、AIに与える情報として整形します。
        # これにより、AIは過去の会話で得たユーザーの情報を踏まえて応答できるようになります。
        memories = get_memories()
        
        # 各カテゴリごとにリストに振り分け
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

        # システムプロンプトの構築
        # AIに対する「役割」や「振る舞い」を定義する最も重要な指示です。
        # データベースから取得した記憶（コンテキスト）をここに埋め込みます（RAG: Retrieval-Augmented Generation の一種）。
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

        # AIに送るメッセージリストを作成
        # system: AIの設定
        # user/assistant: 過去の会話履歴
        # user: 今回の入力
        messages = [{"role": "system", "content": system_prompt}] + self.history + [{"role": "user", "content": user_input}]
        
        # 2. Ollama APIの呼び出し
        try:
            # 非同期クライアントを使用してHTTP POSTリクエストを送信
            async with httpx.AsyncClient() as client:
                response = await client.post(OLLAMA_API_URL, json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": False # ストリーム機能は今回は使わず、一括で返答を受け取ります
                }, timeout=60.0) # タイムアウトを60秒に設定
                
                if response.status_code != 200:
                    result_text = f"エラーが発生しました: {response.text}"
                else:
                    data = response.json()
                    # レスポンスJSONから、AIの応答テキストを取り出します
                    result_text = data.get("message", {}).get("content", "")

        except Exception as e:
            result_text = f"通信エラー: {str(e)}"

        # 3. 履歴の更新
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": result_text})
        
        # 特定のキーワードに対する処理
        # 「ありがとう」と言われたら、区切りとみなして履歴をリセットします。
        if "ありがとう" in user_input:
            self.history = [] # 履歴のクリア
            self.conversation_active = False
        else:
            self.conversation_active = True

        # 4. バックグラウンドタスクの実行: 会話の分析と保存
        # ユーザーへの応答を遅らせないよう、Fire-and-forget（投げっぱなし）で実行します。
        # asyncio.create_task を使うと、現在の処理をブロックせずに別の処理を開始できます。
        asyncio.create_task(self.analyze_and_save(user_input, result_text))
        
        return {
            "response": result_text,
            "context_used": system_prompt if test_mode else None
        }

    # 会話を分析して記憶すべき情報を抽出するメソッド
    async def analyze_and_save(self, user_text, assistant_text):
        # 情報を抽出するための専用プロンプト
        # JSON形式での出力を強制することで、プログラムでの処理を容易にします。
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
                    "format": "json", # OllamaのJSONモードを有効化（モデルが対応している場合）
                    "stream": False
                }, timeout=60.0)
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("message", {}).get("content", "")
                    try:
                        # 文字列としてのJSONをPythonの辞書オブジェクトに変換
                        parsed = json.loads(content)
                        if "items" in parsed and isinstance(parsed["items"], list):
                            for item in parsed["items"]:
                                category = item.get("category")
                                content_str = item.get("content")
                                if category and content_str:
                                    # 有効なカテゴリかチェックしてからデータベースに保存
                                    if category in ['attribute', 'goal', 'memory', 'request']:
                                        add_memory(category, content_str)
                    except json.JSONDecodeError:
                        print("Failed to parse JSON from analysis")
        except Exception as e:
            print(f"Analysis failed: {e}")

