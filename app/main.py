import hashlib, secrets
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import db, llm, memory, tools, harness, agent, prompts
from .config import ROOT, APP_NAME, API_KEY

db.init()
app = FastAPI(title=APP_NAME)

# ---------- auth helpers ----------
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return f"{salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 200_000).hex()}"


def check_pw(pw, stored):
    if not stored:
        return False
    salt = stored.split("$")[0]
    return secrets.compare_digest(hash_pw(pw, salt), stored)


def login_as(resp: Response, member_id):
    token = secrets.token_urlsafe(32)
    db.ex("INSERT INTO sessions(token,member_id) VALUES(?,?)", (token, member_id))
    resp.set_cookie("session", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 14)


def user(request: Request):
    t = request.cookies.get("session")
    u = t and db.one("SELECT m.* FROM sessions s JOIN members m ON m.id=s.member_id WHERE s.token=? AND m.status='active'", (t,))
    if not u:
        raise HTTPException(401, "login required")
    return u


def manager(u=Depends(user)):
    if u["role"] != "manager":
        raise HTTPException(403, "manager only")
    return u


def public(u):
    return {k: u[k] for k in ("id", "name", "email", "role", "lang", "team_id")}


DEFAULT_AGENTS = [
    ("summarize", "Summarize", "Summarize long reports and texts into short, clear summaries."),
    ("email", "Email drafting", "Draft professional emails from the user's notes."),
    ("planning", "Priority planning", "Analyze the user's tasks and suggest a prioritized plan."),
]

# ---------- models ----------
class SignupIn(BaseModel):
    team_name: str; name: str; email: str; password: str = Field(min_length=8)
class LoginIn(BaseModel):
    email: str; password: str
class InviteIn(BaseModel):
    email: str; role: str = "member"
class AcceptIn(BaseModel):
    token: str; name: str; password: str = Field(min_length=8)
class RoleIn(BaseModel):
    role: str
class MsgIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
class TodoIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=80); description: str = Field(min_length=1); requires_approval: bool = True
class ChatIn(BaseModel):
    agent_id: int; message: str = Field(min_length=1, max_length=4000)
class RunIn(BaseModel):
    kind: str; title: str = ""; details: str = ""
class DecisionIn(BaseModel):
    approve: bool; text: str | None = None
class LangIn(BaseModel):
    lang: str

# ---------- auth ----------
@app.post("/api/signup")
def signup(b: SignupIn, resp: Response):
    email = b.email.strip().lower()
    if db.one("SELECT 1 FROM members WHERE email=?", (email,)):
        raise HTTPException(409, "email already registered")
    tid = db.ex("INSERT INTO teams(name) VALUES(?)", (b.team_name.strip(),))
    mid = db.ex("INSERT INTO members(team_id,email,name,pw_hash,role,status) VALUES(?,?,?,?, 'manager','active')",
                (tid, email, b.name.strip(), hash_pw(b.password)))
    for slug, name, desc in DEFAULT_AGENTS:
        db.ex("INSERT INTO tasks(team_id,name,description,slug,is_default,created_by) VALUES(?,?,?,?,1,?)", (tid, name, desc, slug, mid))
    login_as(resp, mid)
    return public(db.one("SELECT * FROM members WHERE id=?", (mid,)))


@app.post("/api/login")
def login(b: LoginIn, resp: Response):
    u = db.one("SELECT * FROM members WHERE email=? AND status='active'", (b.email.strip().lower(),))
    if not u or not check_pw(b.password, u["pw_hash"]):
        raise HTTPException(401, "invalid email or password")
    login_as(resp, u["id"])
    return public(u)


@app.post("/api/logout")
def logout(request: Request, resp: Response):
    t = request.cookies.get("session")
    if t:
        db.ex("DELETE FROM sessions WHERE token=?", (t,))
    resp.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
def me(u=Depends(user)):
    return {**public(u), "app_name": APP_NAME, "mock_ai": not API_KEY}


@app.patch("/api/me/lang")
def set_lang(b: LangIn, u=Depends(user)):
    if b.lang not in ("ar", "en"):
        raise HTTPException(400, "lang must be ar or en")
    db.ex("UPDATE members SET lang=? WHERE id=?", (b.lang, u["id"]))
    return {"lang": b.lang}


@app.post("/api/invite")
def invite(b: InviteIn, u=Depends(manager)):
    email = b.email.strip().lower()
    if b.role not in ("member", "manager"):
        raise HTTPException(400, "bad role")
    if db.one("SELECT 1 FROM members WHERE email=?", (email,)):
        raise HTTPException(409, "email already exists")
    token = secrets.token_urlsafe(24)
    db.ex("INSERT INTO members(team_id,email,role,status,invite_token) VALUES(?,?,?,'invited',?)", (u["team_id"], email, b.role, token))
    return {"invite_link": f"/?invite={token}", "token": token}  # email sending is not implemented: share the link


@app.get("/api/invite/{token}")
def invite_info(token: str):
    m = db.one("SELECT m.email, t.name AS team FROM members m JOIN teams t ON t.id=m.team_id WHERE m.invite_token=? AND m.status='invited'", (token,))
    if not m:
        raise HTTPException(404, "invalid invitation")
    return m


@app.post("/api/accept")
def accept(b: AcceptIn, resp: Response):
    m = db.one("SELECT * FROM members WHERE invite_token=? AND status='invited'", (b.token,))
    if not m:
        raise HTTPException(404, "invalid invitation")
    db.ex("UPDATE members SET name=?,pw_hash=?,status='active',invite_token=NULL WHERE id=?", (b.name.strip(), hash_pw(b.password), m["id"]))
    login_as(resp, m["id"])
    return public(db.one("SELECT * FROM members WHERE id=?", (m["id"],)))

# ---------- members (manager) ----------
@app.get("/api/members")
def members(u=Depends(manager)):
    return db.q("SELECT id,name,email,role,status,invite_token FROM members WHERE team_id=? ORDER BY id", (u["team_id"],))


@app.patch("/api/members/{mid}")
def set_role(mid: int, b: RoleIn, u=Depends(manager)):
    if b.role not in ("member", "manager") or mid == u["id"]:
        raise HTTPException(400, "invalid change")
    db.ex("UPDATE members SET role=? WHERE id=? AND team_id=?", (b.role, mid, u["team_id"]))
    return {"ok": True}


@app.delete("/api/members/{mid}")
def remove_member(mid: int, u=Depends(manager)):
    if mid == u["id"]:
        raise HTTPException(400, "cannot remove yourself")
    if db.one("SELECT 1 FROM members WHERE id=? AND team_id=?", (mid, u["team_id"])):
        _erase(mid)
    return {"ok": True}

# ---------- channel, todos, home ----------
@app.get("/api/messages")
def messages(limit: int = 50, u=Depends(user)):
    limit = max(1, min(limit, 200))
    return db.q("SELECT m.id,m.content,m.source,m.created_at,m.member_id,COALESCE(p.name,'?') AS who FROM messages m "
                "LEFT JOIN members p ON p.id=m.member_id WHERE m.team_id=? ORDER BY m.id DESC LIMIT ?", (u["team_id"], limit))[::-1]


@app.post("/api/messages")
def post_message(b: MsgIn, u=Depends(user)):
    return {"id": tools._post(u["team_id"], u["id"], b.content.strip(), "human")}


@app.get("/api/todos")
def todos(u=Depends(user)):
    return db.q("SELECT id,title,status,created_at FROM todos WHERE member_id=? ORDER BY id DESC", (u["id"],))


@app.post("/api/todos")
def add_todo(b: TodoIn, u=Depends(user)):
    return {"id": db.ex("INSERT INTO todos(member_id,title) VALUES(?,?)", (u["id"], b.title.strip()))}


@app.patch("/api/todos/{tid}")
def done_todo(tid: int, u=Depends(user)):
    db.ex("UPDATE todos SET status='done' WHERE id=? AND member_id=?", (tid, u["id"]))
    return {"ok": True}


@app.get("/api/stats")
def stats(u=Depends(user)):
    t = u["team_id"]
    c = lambda sql, a: db.one(sql, a)["n"]
    return {"members": c("SELECT COUNT(*) n FROM members WHERE team_id=? AND status='active'", (t,)),
            "messages": c("SELECT COUNT(*) n FROM messages WHERE team_id=?", (t,)),
            "tasks": c("SELECT COUNT(*) n FROM runs WHERE team_id=? AND kind!='chat'", (t,)),
            "agents": c("SELECT COUNT(*) n FROM tasks WHERE team_id=?", (t,))}


@app.get("/api/home")
def home(u=Depends(user)):
    pending = db.q("SELECT id,title,'todo' AS type FROM todos WHERE member_id=? AND status='open' ORDER BY id DESC LIMIT 10", (u["id"],))
    pending += db.q("SELECT id,title,'approval' AS type FROM runs WHERE member_id=? AND status='awaiting_approval'", (u["id"],))
    return {"stats": stats(u), "pending": pending, "recent_messages": messages(5, u)}

# ---------- tasks / agents ----------
@app.get("/api/tasks")
def list_tasks(u=Depends(user)):
    return db.q("SELECT id,name,description,slug,requires_approval,is_default,created_by FROM tasks WHERE team_id=? ORDER BY id", (u["team_id"],))


@app.post("/api/tasks")
def create_task(b: TaskIn, u=Depends(user)):
    tid = db.ex("INSERT INTO tasks(team_id,name,description,requires_approval,created_by) VALUES(?,?,?,?,?)",
                (u["team_id"], b.name.strip(), b.description.strip(), int(b.requires_approval), u["id"]))
    return db.one("SELECT * FROM tasks WHERE id=?", (tid,))  # appears in GET /api/tasks => a chip in My Assistant


@app.delete("/api/tasks/{tid}")
def delete_task(tid: int, u=Depends(user)):
    t = db.one("SELECT * FROM tasks WHERE id=? AND team_id=?", (tid, u["team_id"]))
    if not t or t["is_default"] or (t["created_by"] != u["id"] and u["role"] != "manager"):
        raise HTTPException(403, "not allowed")
    db.ex("DELETE FROM tasks WHERE id=?", (tid,))
    return {"ok": True}

# ---------- assistant chat ----------
def _agent(agent_id, u):
    a = db.one("SELECT * FROM tasks WHERE id=? AND team_id=?", (agent_id, u["team_id"]))
    if not a:
        raise HTTPException(404, "agent not found")
    return a


@app.get("/api/chat/{agent_id}")
def chat_history(agent_id: int, u=Depends(user)):
    _agent(agent_id, u)
    return [r for r in memory.history(u["id"], agent_id) if r["role"] != "summary"]


@app.delete("/api/chat/{agent_id}")
def chat_reset(agent_id: int, u=Depends(user)):
    db.ex("DELETE FROM conversations WHERE member_id=? AND agent_id=?", (u["id"], agent_id))
    return {"ok": True}


@app.post("/api/chat")
def chat(b: ChatIn, u=Depends(user)):
    a = _agent(b.agent_id, u)
    try:
        harness.check_and_count(u["id"])
    except harness.CapExceeded as e:
        raise HTTPException(429, str(e))
    related = tools.search_scored(u["team_id"], b.message, 5)          # retrieval, not a full dump
    msgs = [{"role": "system", "content": prompts.scope(a, related)}] + memory.build(u["id"], a["id"]) + [{"role": "user", "content": b.message}]
    try:
        r = llm.chat(msgs)
    except llm.LLMError as e:
        raise HTTPException(502, str(e))
    memory.add(u["id"], a["id"], "user", b.message)
    memory.add(u["id"], a["id"], "assistant", r["content"])
    harness.log_chat(u, a["name"], r["tokens"])
    return {"reply": r["content"], "model": r["model"]}

# ---------- agent runs (tools + approval) ----------
@app.post("/api/runs")
def new_run(b: RunIn, u=Depends(user)):
    try:
        return agent.start(u, b.kind, b.title, b.details)
    except harness.CapExceeded as e:
        raise HTTPException(429, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/runs")
def my_runs(u=Depends(user)):
    return db.q("SELECT id,kind,title,status,exit_reason,tokens,cost,created_at FROM runs WHERE member_id=? AND kind!='chat' ORDER BY id DESC LIMIT 50", (u["id"],))


@app.get("/api/runs/{rid}")
def run_detail(rid: int, u=Depends(user)):
    r = agent.get(rid)
    if not r or (r["member_id"] != u["id"] and not (u["role"] == "manager" and r["team_id"] == u["team_id"])):
        raise HTTPException(404, "run not found")
    return r


@app.post("/api/runs/{rid}/decision")
def run_decision(rid: int, b: DecisionIn, u=Depends(user)):
    try:
        return agent.decide(rid, u, b.approve, b.text)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/traces")
def traces(u=Depends(manager)):
    rows = db.q("SELECT r.id,r.kind,r.title,r.status,r.exit_reason,r.config,r.tokens,r.cost,r.steps,r.created_at,COALESCE(m.name,m.email) AS who "
                "FROM runs r LEFT JOIN members m ON m.id=r.member_id WHERE r.team_id=? ORDER BY r.id DESC LIMIT 100", (u["team_id"],))
    import json
    for r in rows:
        s = json.loads(r.pop("steps") or "[]")
        r["tool_calls"] = [x["name"] for x in s if x["type"] == "tool"]
        r["steps"] = len(s)
    return rows

# ---------- PDPL: delete my data ----------
def _erase(mid):
    m = db.one("SELECT * FROM members WHERE id=?", (mid,))
    if not m:
        return
    runs = [r["id"] for r in db.q("SELECT id FROM runs WHERE member_id=?", (mid,))]
    for rid in runs:
        db.ex("DELETE FROM approvals WHERE run_id=?", (rid,))
    for sql in ("DELETE FROM runs WHERE member_id=?", "DELETE FROM conversations WHERE member_id=?", "DELETE FROM todos WHERE member_id=?",
                "DELETE FROM messages WHERE member_id=?", "DELETE FROM sessions WHERE member_id=?", "DELETE FROM usage WHERE member_id=?",
                "DELETE FROM members WHERE id=?"):
        db.ex(sql, (mid,))


@app.delete("/api/me")
def delete_me(resp: Response, u=Depends(user)):
    others = db.one("SELECT COUNT(*) n FROM members WHERE team_id=? AND id!=?", (u["team_id"], u["id"]))["n"]
    if u["role"] == "manager" and others:
        raise HTTPException(409, "transfer the manager role or remove the other members first")
    _erase(u["id"])
    if not others:
        for sql in ("DELETE FROM tasks WHERE team_id=?", "DELETE FROM messages WHERE team_id=?", "DELETE FROM teams WHERE id=?"):
            db.ex(sql, (u["team_id"],))
    resp.delete_cookie("session")
    return {"ok": True}


STATIC = ROOT / "static"
if STATIC.exists():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
