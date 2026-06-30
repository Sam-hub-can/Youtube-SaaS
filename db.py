import psycopg2
import os

DB_URL = os.getenv("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DB_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS replies (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        video TEXT,
        comment TEXT,
        reply TEXT,
        status TEXT DEFAULT 'pending'
    )
    """)

    conn.commit()
    conn.close()


def insert_reply(data):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO replies VALUES (%s,%s,%s,%s,%s,%s)
    ON CONFLICT (id) DO NOTHING
    """, (
        data["id"],
        data["user_id"],
        data["video"],
        data["comment"],
        data["reply"],
        "pending"
    ))

    conn.commit()
    conn.close()


def get_pending(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM replies WHERE user_id=%s AND status='pending'", (user_id,))
    rows = cur.fetchall()

    conn.close()
    return rows


def approve(reply_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("UPDATE replies SET status='approved' WHERE id=%s", (reply_id,))
    conn.commit()
    conn.close()
