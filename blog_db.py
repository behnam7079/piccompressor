import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blog.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        meta_desc TEXT NOT NULL,
        keywords TEXT NOT NULL,
        content TEXT NOT NULL,
        reading_time INTEGER DEFAULT 3,
        status TEXT DEFAULT 'published',
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def get_all_posts(limit=20, offset=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, slug, title, meta_desc, reading_time, created_at FROM posts WHERE status = 'published' ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    posts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return posts

def get_post_by_slug(slug: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE slug = ? AND status = 'published'", (slug,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_slugs_for_sitemap():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT slug, created_at FROM posts WHERE status = 'published' ORDER BY id DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def insert_post(slug: str, title: str, meta_desc: str, keywords: str, content: str, reading_time: int = 3, status: str = 'published'):
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d")
    try:
        cursor.execute("""
        INSERT INTO posts (slug, title, meta_desc, keywords, content, reading_time, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (slug, title, meta_desc, keywords, content, reading_time, status, created_at))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# ساخت جدول در اولین اجرا
init_db()
