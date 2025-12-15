# AI秘書 (Memory Assistant v2)

PROMPT_DESIGN.mdに基づくAI秘書アプリケーション。

## 機能
- **チャットUI**: ユーザーの入力に応答し、記憶を蓄積します。
- **自動記憶**: Ollamaを使用して会話からユーザーの属性、目標、記憶、要望を自動的に抽出しSQLiteに保存します。
- **コンテキスト管理**: 5分経過または「ありがとう」と入力すると、コンテキスト（短期記憶）をリセットします。
- **DB管理画面**: 蓄積された記憶の確認、編集、削除が可能です。
- **テストモード**: AIに送信されているシステムプロンプトとコンテキストを確認できます。

## 必要条件
- Python 3.8+
- [Ollama](https://ollama.com/) (デフォルトで `llama3` モデルを使用しますが、`ai_engine.py` で変更可能)
  - 実行前に `ollama pull llama3` (または使用したいモデル) を実行してください。

## インストール
```bash
pip install -r requirements.txt
```

## 実行方法
```bash
uvicorn main:app --reload
```
ブラウザで `http://localhost:8000` にアクセスしてください。

## 構成
- `main.py`: FastAPIアプリケーションのエントリーポイント
- `ai_engine.py`: Ollamaとの通信、コンテキスト管理、記憶抽出ロジック
- `database.py`: SQLiteデータベース操作
- `static/`: フロントエンド (HTML/CSS/JS)
