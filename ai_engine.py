# httpx: 非同期HTTPリクエストを行うためのライブラリ。AI APIへの通信に使用します。
import httpx
import time
import json
import asyncio
from memory_mcp import memory_mcp_server

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
        
        # 1. コンテキスト（長期記憶）の取得 - MCP経由に変更
        # MCPサーバーからリソースを取得します。
        formatted_memories = memory_mcp_server.read_resource("memories://active")
        
        attributes = [m['content'] for m in formatted_memories["attributes"]]
        goals = [m['content'] for m in formatted_memories["goals"]]
        requests = [m['content'] for m in formatted_memories["requests"]]
        memory_list = [m['content'] for m in formatted_memories["memories"]]
        
        # システムプロンプトの構築
        # AIに対する「役割」や「振る舞い」を定義する最も重要な指示です。
        # MCPから取得した記憶（コンテキスト）をここに埋め込みます。
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

        # 4. バックグラウンドタスクの実行 -> 変更: テストモードでログを表示するためAwaitします
        # analysis_log: { "prompt": str, "response": str }
        analysis_log = await self.analyze_and_save(user_input)
        
        return {
            "response": result_text,
            "debug_info": {
                "chat_messages": messages, # 送信した全メッセージ（システムプロンプト含む）
                "analysis_log": analysis_log
            }
        }

    # 会話を分析して記憶すべき情報を抽出するメソッド
    async def analyze_and_save(self, user_text):
        # 情報を抽出するための専用プロンプト
        # JSON形式での出力を強制することで、プログラムでの処理を容易にします。
        # AIの応答は含めず、ユーザーの発言のみを対象とします。
        prompt = f"""
以下のユーザーの入力から、長期的に保存すべきユーザーの情報（属性、目標、記憶、アシスタントへの要望）を抽出してください。
保存すべき情報がない場合は、"items": [] としてください。
JSON形式のみで出力してください。Markdownのコードブロックは不要です。

重要: 以下の「フォーマット例」に記載されている内容（プログラマーである、Pythonをマスターしたい等）は、あくまで形式の例です。
実際の入力に含まれていない限り、絶対に出力に含めないでください。

フォーマット例:
{{
    "items": [
        {{ "category": "attribute", "content": "ユーザーはプログラマーである" }},
        {{ "category": "goal", "content": "ユーザーはPythonをマスターしたい" }},
        {{ "category": "request", "content": "返答は短くしてほしい" }}
    ]
}}

有効なカテゴリ: attribute (属性), goal (目標), memory (一般記憶), request (要望)

[ユーザーの入力]
{user_text}
"""
        result_log = {"prompt": prompt, "response": "", "parsed": None}

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
                    result_log["response"] = content
                    try:
                        # 文字列としてのJSONをPythonの辞書オブジェクトに変換
                        parsed = json.loads(content)
                        result_log["parsed"] = parsed
                        if "items" in parsed and isinstance(parsed["items"], list):
                            for item in parsed["items"]:
                                category = item.get("category")
                                content_str = item.get("content")
                                if category and content_str:
                                    # 有効なカテゴリかチェックしてからデータベースに保存
                                    if category in ['attribute', 'goal', 'memory', 'request']:
                                        # MCP経由で保存（Tool call）
                                        memory_mcp_server.call_tool("add_memory", {"category": category, "content": content_str})
                    except json.JSONDecodeError:
                        print("Failed to parse JSON from analysis")
                        result_log["error"] = "Failed to parse JSON from analysis"
                else:
                    result_log["error"] = f"LLM error: {response.text}"
        except Exception as e:
            print(f"Analysis failed: {e}")
            result_log["error"] = str(e)
        
        return result_log

    # 記憶の圧縮・統合を行うメソッド（ストリーミング版）
    # ステップバイステップで実行し、ログをyieldで返します。
    async def compress_memories_stream(self):
        import datetime
        
        yield json.dumps({"step": "start", "message": "記憶の整理プロセスを開始します..."}) + "\n"
        
        # 1. 全記憶の取得 (MCP経由)
        memories = memory_mcp_server.read_resource("memories://all")
        if not memories:
            yield json.dumps({"step": "end", "message": "記憶がありません。終了します。"}) + "\n"
            return

        # カテゴリごとに処理
        categories = ['attribute', 'goal', 'request', 'memory']
        
        for category in categories:
            cat_memories = [m for m in memories if m['category'] == category]
            if not cat_memories:
                continue
            
            yield json.dumps({"step": "category_start", "message": f"\n--- カテゴリ: {category} ({len(cat_memories)}件) の整理を開始 ---"}) + "\n"

            # ---------------------------------------------------------
            # 3.1 & 3.2: 重複/類似の意味を持つ情報の統合
            # ---------------------------------------------------------
            yield json.dumps({"step": "process", "message": "類似した意味を持つ記憶を探索中..."}) + "\n"
            
            # リストをJSON化
            items_json = json.dumps([{"id": m["id"], "content": m["content"]} for m in cat_memories], ensure_ascii=False)
            
            prompt_similarity = f"""
以下の記憶リストから、意味が重複している、または非常に似ている項目のグループを探してください。
グループがない場合は空のリストを返してください。

リスト:
{items_json}

出力フォーマット(JSON):
{{
    "groups": [
        [ID1, ID2],
        [ID3, ID4, ID5]
    ]
}}
"""
            groups = await self._call_llm_json(prompt_similarity)
            
            if groups and "groups" in groups and groups["groups"]:
                for group_ids in groups["groups"]:
                    if len(group_ids) < 2: continue
                    
                    # 該当する記憶の内容を取得
                    targets = [m for m in cat_memories if m["id"] in group_ids]
                    if len(targets) < 2: continue
                    
                    yield json.dumps({"step": "action", "message": f"類似項目を統合します: {[t['content'] for t in targets]}"}) + "\n"
                    
                    # 統合プロンプト
                    contents = "\n".join([f"- {t['content']}" for t in targets])
                    prompt_merge = f"""
以下の複数の情報を、意味を損なわない範囲で最も単純で明確な一つの文にまとめてください。

{contents}

出力は統合後の文のみを返してください。JSON不要。
"""
                    merged_content = await self._call_llm_text(prompt_merge)
                    
                    # DB更新 (MCP経由)
                    # 古いものを削除
                    for t in targets:
                        memory_mcp_server.call_tool("delete_memory", {"id": t["id"]})
                        # ローカルリストからも削除（以降の処理のため）
                        cat_memories = [m for m in cat_memories if m["id"] != t["id"]]

                    # 新しいものを追加
                    memory_mcp_server.call_tool("add_memory", {"category": category, "content": merged_content})
                    yield json.dumps({"step": "result", "message": f"統合完了 -> {merged_content}"}) + "\n"
            else:
                yield json.dumps({"step": "info", "message": "統合すべき類似項目はありませんでした。"}) + "\n"

            # ---------------------------------------------------------
            # 3.4: 矛盾する内容の整合性チェック
            # ---------------------------------------------------------
            # リロード（統合で変わったため）
            # ここでは簡易的に、現在の cat_memories を見直すのではなく、再度読み込むのが安全だがパフォーマンス上省略し、
            # 残っているものでチェックします。
            
            if len(cat_memories) >= 2:
                yield json.dumps({"step": "process", "message": "矛盾する内容の探索中..."}) + "\n"
                items_json = json.dumps([{"id": m["id"], "content": m["content"], "created_at": m["created_at"]} for m in cat_memories], ensure_ascii=False)
                
                prompt_contradiction = f"""
以下の記憶リストの中に、論理的に矛盾する（両立しない）項目のペアはありますか？
矛盾がある場合、作成日時（created_at）が古い方のIDを指摘してください。

リスト:
{items_json}

出力フォーマット(JSON):
{{
    "contradictions": [
        {{ "ids": [ID1, ID2], "reason": "矛盾の理由", "older_id": ID1 }}
    ]
}}
矛盾がない場合は "contradictions": []
"""
                contradictions = await self._call_llm_json(prompt_contradiction)
                
                if contradictions and "contradictions" in contradictions and contradictions["contradictions"]:
                    for cont in contradictions["contradictions"]:
                        older_id = cont.get("older_id")
                        if older_id:
                            target = next((m for m in cat_memories if m["id"] == older_id), None)
                            if target:
                                yield json.dumps({"step": "action", "message": f"矛盾を検出 ({cont.get('reason')})。古い記憶を削除: {target['content']}"}) + "\n"
                                memory_mcp_server.call_tool("delete_memory", {"id": older_id})
                                cat_memories = [m for m in cat_memories if m["id"] != older_id]
                else:
                    yield json.dumps({"step": "info", "message": "矛盾点は見つかりませんでした。"}) + "\n"

            # ---------------------------------------------------------
            # 3.3: 長い文章の短縮
            # ---------------------------------------------------------
            yield json.dumps({"step": "process", "message": "長い文章の短縮チェック中..."}) + "\n"
            for m in cat_memories:
                if len(m["content"]) > 15:
                    prompt_shorten = f"""
以下の文を、意味を損なわない範囲でできるだけ短くシンプルに書き直してください。
元の文の意味が完全に保たれる場合のみ変更してください。

文: {m['content']}

出力は書き直した文のみ。
"""
                    shortened = await self._call_llm_text(prompt_shorten)
                    shortened = shortened.strip()
                    
                    if len(shortened) < len(m["content"]) and shortened != m["content"]:
                         yield json.dumps({"step": "action", "message": f"短縮: {m['content']} -> {shortened}"}) + "\n"
                         memory_mcp_server.call_tool("update_memory", {"id": m["id"], "content": shortened, "category": category})

        yield json.dumps({"step": "complete", "message": "全ての整理プロセスが完了しました。"}) + "\n"

    # ヘルパー: LLMを呼んでJSONを返す
    async def _call_llm_json(self, prompt):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(OLLAMA_API_URL, json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "format": "json",
                    "stream": False
                }, timeout=120.0)
                if response.status_code == 200:
                    return json.loads(response.json().get("message", {}).get("content", "{}"))
        except:
            return {}
        return {}

    # ヘルパー: LLMを呼んでテキストを返す
    async def _call_llm_text(self, prompt):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(OLLAMA_API_URL, json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }, timeout=120.0)
                if response.status_code == 200:
                    return response.json().get("message", {}).get("content", "")
        except:
            return ""
        return ""

