import os
import sqlite3
from datetime import datetime

# تعیین نوع دیتابیس (اگر DATABASE_URL باشد یعنی روی رندر هستیم)
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    if DATABASE_URL:
        # اتصال به PostgreSQL (Supabase)
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        # برای اینکه نتیجه‌ها مثل دیتکتوری (Dict) برگردند
        return conn, conn.cursor(cursor_factory=RealDictCursor)
    else:
        # اتصال به SQLite محلی
        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blog.db")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, conn.cursor()

def init_db():
    conn, cursor = get_connection()
    # در PostgreSQL از SERIAL و در SQLite از INTEGER PRIMARY KEY استفاده می‌کنیم
    if DATABASE_URL:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
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
    else:
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

# تابعی کمکی برای اجرای کوئری‌ها (پشتیبانی از ؟ در SQLite و %s در Postgres)
def execute_query(query, params=(), fetch=False):
    conn, cursor = get_connection()
    # تبدیل علامت سوال به فرمت Postgres اگر لازم باشد
    if DATABASE_URL:
        query = query.replace("?", "%s")
    
    cursor.execute(query, params)
    
    result = None
    if fetch:
        result = cursor.fetchall()
        
    conn.commit()
    conn.close()
    return result

def get_all_posts(limit=20, offset=0):
    query = "SELECT id, slug, title, meta_desc, reading_time, created_at FROM posts WHERE status = 'published' ORDER BY id DESC LIMIT ? OFFSET ?"
    rows = execute_query(query, (limit, offset), fetch=True)
    return [dict(row) for row in rows]

def get_post_by_slug(slug: str):
    query = "SELECT * FROM posts WHERE slug = ? AND status = 'published'"
    rows = execute_query(query, (slug,), fetch=True)
    return dict(rows[0]) if rows else None

def get_all_slugs_for_sitemap():
    query = "SELECT slug, created_at FROM posts WHERE status = 'published' ORDER BY id DESC"
    rows = execute_query(query, fetch=True)
    return [dict(row) for row in rows]

def insert_post(slug: str, title: str, meta_desc: str, keywords: str, content: str, reading_time: int = 3, status: str = 'published'):
    created_at = datetime.now().strftime("%Y-%m-%d")
    query = """
    INSERT INTO posts (slug, title, meta_desc, keywords, content, reading_time, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        execute_query(query, (slug, title, meta_desc, keywords, content, reading_time, status, created_at))
        return True
    except:
        return False

def get_all_posts_admin():
    query = "SELECT id, slug, title, created_at FROM posts ORDER BY id DESC"
    rows = execute_query(query, fetch=True)
    return [dict(row) for row in rows]

def delete_post_by_id(post_id: int):
    execute_query("DELETE FROM posts WHERE id = ?", (post_id,))

# اجرای اولیه
init_db()
