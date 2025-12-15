# FastAPI: 高速でモダンなWeb API構築のためのフレームワーク
# 非同期処理（async/await）をネイティブにサポートしており、AIのような待ち時間の発生する処理と相性が良いです。
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
# Pydantic: データのバリデーション（検証）や設定管理を行うライブラリ
# 型ヒントを使って、APIが受け取るデータの形式を定義します。
from pydantic import BaseModel
from typing import List, Optional
import os
# 自作のモジュールをインポート
from database import init_db, get_memories, add_memory, delete_memory, update_memory
from ai_engine import AIEngine

# アプリケーションのインスタンスを作成
# これがWebサーバーの本体になります。
app = FastAPI(title="AI Secretary")

# データベースの初期化
# アプリケーション起動時にテーブルが存在しなければ作成します。
init_db()

# AIエンジンの初期化
# 会話の履歴管理やLLMとの通信を行うクラスのインスタンスを作成します。
ai_engine = AIEngine()

# Staticファイルのマウント
# "/static" というURLで、"static" フォルダ内のファイル（CSS, JS, 画像など）にアクセスできるようにします。
# これにより、ブラウザから http://localhost:8000/static/style.css などが見えるようになります。
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydanticモデルの定義
# APIが受け取るデータの「型」を定義します。
# これにより、不正なデータが送られてきた場合に自動ではじくことができます。
class ChatRequest(BaseModel):
    message: str          # 必須項目：ユーザーからのメッセージ
    test_mode: bool = False # オプション項目：デフォルトはFalse

class ChatResponse(BaseModel):
    response: str
    debug_info: Optional[dict] = None # テストモード用の詳細ログ（プロンプト、分析結果など）

class MemoryItem(BaseModel):
    category: str
    content: str

class MemoryUpdate(BaseModel):
    category: str
    content: str

# ルーティングの定義
# @app.get("/") は、ルートURL（http://localhost:8000/）へのGETアクセスに対する処理を定義します。
# async def: 非同期関数として定義。重い処理（AI応答など）の実行中に、他のリクエストをブロックせずに受け付けられます。
@app.get("/")
async def read_root():
    # HTMLファイルをそのまま返します。ブラウザはこれを受け取って表示します。
    return FileResponse("static/index.html")

@app.get("/admin")
async def read_admin():
    return FileResponse("static/admin.html")

# AIとのチャット用エンドポイント
# POSTメソッドを使用します（データを送信して処理させるため）。
# response_modelを指定することで、返却値の形式を保証し、自動的にドキュメント生成にも使われます。
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # ai_engine.chatメソッドを呼び出して、入力に対する応答を生成
    # awaitを使うことで、AIの応答待ちの間、CPUを解放します。
    result = await ai_engine.chat(request.message, request.test_mode)
    return ChatResponse(
        response=result["response"],
        debug_info=result.get("debug_info")
    )

# 記憶データの取得用API
# クエリパラメータ category を受け取ります（例: /api/memories?category=goal）
# Optional[str] = None とすることで、categoryは必須ではなくなります。
@app.get("/api/memories")
async def get_all_memories(category: Optional[str] = None):
    return get_memories(category)

# 記憶の追加用API
@app.post("/api/memories")
async def create_memory(item: MemoryItem):
    add_memory(item.category, item.content)
    return {"status": "success"}

# 記憶の更新用API
# URLパスの一部（{memory_id}）を変数として受け取ります。
@app.put("/api/memories/{memory_id}")
async def update_memory_item(memory_id: int, item: MemoryUpdate):
    update_memory(memory_id, item.content, item.category)
    return {"status": "success"}

# 記憶の削除用API
@app.delete("/api/memories/{memory_id}")
async def delete_memory_item(memory_id: int):
    delete_memory(memory_id)
    return {"status": "success"}

# 記憶の圧縮実行API
# 管理画面などから手動で呼び出します。
@app.post("/api/memories/compress")
async def compress_memories_endpoint():
    result = await ai_engine.compress_memories()
    return result

# このファイルが直接実行された場合（python main.py）、サーバーを起動します。
# uvicornは、FastAPIを動かすための高速なASGIサーバーです。
# reload=True にすると、コードを保存するたびに自動で再起動して便利です（開発用）。
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
