import sqlite3, threading
from .config import DB_PATH

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL, email TEXT UNIQUE NOT NULL,
  name TEXT, pw_hash TEXT, role TEXT NOT NULL DEFAULT 'member', status TEXT NOT NULL DEFAULT 'invited',
  invite_token TEXT, lang TEXT DEFAULT 'en');
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, member_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL, name TEXT NOT NULL,
  description TEXT NOT NULL, slug TEXT, requires_approval INTEGER DEFAULT 1, is_default INTEGER DEFAULT 0, created_by INTEGER);
CREATE TABLE IF NOT EXISTS todos(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, title TEXT NOT NULL,
  status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL, member_id INTEGER,
  content TEXT NOT NULL, source TEXT DEFAULT 'human', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, agent_id INTEGER NOT NULL,
  role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, team_id INTEGER, member_id INTEGER, kind TEXT, title TEXT,
  status TEXT, exit_reason TEXT, config TEXT, steps TEXT DEFAULT '[]', state TEXT, result TEXT,
  tokens INTEGER DEFAULT 0, cost REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, member_id INTEGER NOT NULL,
  draft TEXT NOT NULL, final_text TEXT, status TEXT DEFAULT 'pending', posted INTEGER DEFAULT 0, decided_at TEXT);
CREATE TABLE IF NOT EXISTS usage(member_id INTEGER, day TEXT, n INTEGER DEFAULT 0, PRIMARY KEY(member_id, day));
CREATE TABLE IF NOT EXISTS llm_cache(key TEXT PRIMARY KEY, value TEXT);
"""


def conn():
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        _local.c = c
    return c


def init():
    conn().executescript(SCHEMA)


def q(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql, args=()):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def ex(sql, args=()):
    c = conn()
    cur = c.execute(sql, args)
    c.commit()
    return cur.lastrowid
