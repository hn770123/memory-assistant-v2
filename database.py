import sqlite3
from datetime import datetime

DB_FILE = "memory_assistant.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL, -- attribute, goal, memory, request
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_memory(category, content):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO memories (category, content) VALUES (?, ?)', (category, content))
    conn.commit()
    conn.close()

def get_memories(category=None):
    conn = get_db_connection()
    c = conn.cursor()
    if category:
        c.execute('SELECT * FROM memories WHERE category = ? ORDER BY created_at DESC', (category,))
    else:
        c.execute('SELECT * FROM memories ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_memory(memory_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM memories WHERE id = ?', (memory_id,))
    conn.commit()
    conn.close()

def update_memory(memory_id, content, category):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE memories SET content = ?, category = ? WHERE id = ?', (content, category, memory_id))
    conn.commit()
    conn.close()
