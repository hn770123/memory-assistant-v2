import sqlite3
from datetime import datetime

# データベースファイルの名前
# このファイルに全ての記憶が保存されます。アプリケーションと同じフォルダに作成されます。
DB_FILE = "memory_assistant.db"

# データベース接続を取得するヘルパー関数
# sqlite3.connect() でデータベースに接続します。
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    # Rowファクトリを設定することで、カラム名でデータにアクセスできるようになります。
    # 例: row['category'] のようにアクセス可能（辞書のように扱える）
    conn.row_factory = sqlite3.Row
    return conn

# データベースの初期化関数
# テーブルが存在しない場合に作成（CREATE TABLE）します。
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # SQLを実行してテーブルを作成
    # IF NOT EXISTS: すでにテーブルがある場合は何もしない
    # id: 一意な識別子 (PRIMARY KEY)
    # category: 記憶の種類（属性、目標、記憶、要望）
    # content: 記憶の内容
    # created_at: 作成日時（デフォルトで現在時刻を入れる）
    c.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL, -- attribute, goal, memory, request
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit() # 変更を確定
    conn.close()  # 接続を閉じる

# 記憶を追加する関数
# INSERT文を使ってデータを挿入します。
def add_memory(category, content):
    conn = get_db_connection()
    c = conn.cursor()
    # SQLインジェクションを防ぐため、プレースホルダー（?）を使用します。
    # 第2引数のタプル (category, content) が ? に代入されます。
    c.execute('INSERT INTO memories (category, content) VALUES (?, ?)', (category, content))
    conn.commit()
    conn.close()

# 記憶を取得する関数
# SELECT文を使ってデータを取得します。
def get_memories(category=None):
    conn = get_db_connection()
    c = conn.cursor()
    if category:
        # カテゴリ指定がある場合
        c.execute('SELECT * FROM memories WHERE category = ? ORDER BY created_at DESC', (category,))
    else:
        # 全ての記憶を取得する場合
        c.execute('SELECT * FROM memories ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    # sqlite3.RowオブジェクトをPythonの辞書に変換して返します
    return [dict(row) for row in rows]

# 記憶を削除する関数
# DELETE文を使ってデータを削除します。
def delete_memory(memory_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM memories WHERE id = ?', (memory_id,))
    conn.commit()
    conn.close()

# 記憶を更新する関数
# UPDATE文を使ってデータを書き換えます。
def update_memory(memory_id, content, category):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE memories SET content = ?, category = ? WHERE id = ?', (content, category, memory_id))
    conn.commit()
    conn.close()

# 全ての記憶を削除する関数（圧縮機能などで使用）
# 十分に注意して使用する必要があります。
def delete_all_memories():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM memories')
    # IDの自動採番（AUTOINCREMENT）をリセットする場合（任意）
    # c.execute('DELETE FROM sqlite_sequence WHERE name="memories"')
    conn.commit()
    conn.close()
