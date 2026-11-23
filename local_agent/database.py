import sqlite3
import json
import datetime
import config


def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT,
        product_name TEXT,
        description TEXT,
        price TEXT,
        company_info_file TEXT,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS business_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        profile_json TEXT,
        source TEXT,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS icps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        icp_json TEXT,
        source TEXT,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS prospects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        company TEXT,
        website TEXT,
        contact_name TEXT,
        contact_role TEXT,
        email TEXT,
        industry TEXT,
        employees INTEGER,
        location TEXT,
        page_text TEXT,
        research_json TEXT,
        signals_json TEXT,
        problem_statement TEXT,
        score INTEGER,
        score_reason TEXT,
        status TEXT DEFAULT 'new',
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_id INTEGER,
        subject TEXT,
        body TEXT,
        source TEXT,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_id INTEGER,
        reply_text TEXT,
        label TEXT,
        confidence REAL,
        suggested_action TEXT,
        source TEXT,
        created_at TEXT
    )""")
    # tasks that failed because ollama was down
    c.execute("""CREATE TABLE IF NOT EXISTS task_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT,
        payload TEXT,
        status TEXT DEFAULT 'pending',
        error TEXT,
        created_at TEXT,
        done_at TEXT
    )""")
    conn.commit()
    conn.close()


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def query(sql, params=(), one=False):
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=()):
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


# ---- small helpers ----

def add_product(company_name, product_name, description, price, info_file):
    return execute(
        "INSERT INTO products (company_name, product_name, description, price, company_info_file, created_at) VALUES (?,?,?,?,?,?)",
        (company_name, product_name, description, price, info_file, now()))


def get_product(pid):
    return query("SELECT * FROM products WHERE id=?", (pid,), one=True)


def save_profile(pid, profile, source):
    execute("INSERT INTO business_profiles (product_id, profile_json, source, created_at) VALUES (?,?,?,?)",
            (pid, json.dumps(profile), source, now()))


def latest_profile(pid):
    row = query("SELECT * FROM business_profiles WHERE product_id=? ORDER BY id DESC LIMIT 1", (pid,), one=True)
    if row:
        return json.loads(row["profile_json"])
    return None


def save_icp(pid, icp, source):
    execute("INSERT INTO icps (product_id, icp_json, source, created_at) VALUES (?,?,?,?)",
            (pid, json.dumps(icp), source, now()))


def latest_icp(pid):
    row = query("SELECT * FROM icps WHERE product_id=? ORDER BY id DESC LIMIT 1", (pid,), one=True)
    if row:
        return json.loads(row["icp_json"])
    return None


def add_to_queue(task_type, payload, error):
    return execute("INSERT INTO task_queue (task_type, payload, status, error, created_at) VALUES (?,?,?,?,?)",
                   (task_type, json.dumps(payload), "pending", error, now()))


if __name__ == "__main__":
    init_db()
    print("db created at", config.DB_PATH)
