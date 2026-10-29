import asyncio, os, re, sys
from . import db
from .config import ROOT

SCHEMAS = {
    "read_team_messages": {"description": "Read the latest messages in the team channel.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "max 30"}}, "required": []}},
    "list_my_tasks": {"description": "List the current user's open to-do items.",
        "parameters": {"type": "object", "properties": {}, "required": []}},
    "search_team_messages": {"description": "Search team messages by keywords (served over MCP).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    "post_to_team_channel": {"description": "Post a message to the team channel. Requires human approval.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
}

# Least privilege: each task kind gets only the tools it needs (enforced in the agent loop).
KIND_TOOLS = {
    "summary": ["read_team_messages", "search_team_messages"],
    "planning": ["list_my_tasks"],
    "announcement": ["read_team_messages", "list_my_tasks", "search_team_messages", "post_to_team_channel"],
}
UNTRUSTED = {"read_team_messages", "search_team_messages", "list_my_tasks"}


def schemas(names):
    return [{"type": "function", "function": {"name": n, **SCHEMAS[n]}} for n in names]


def _rows(team_id, limit):
    return db.q("SELECT m.id, COALESCE(p.name,'?') AS who, m.content FROM messages m "
                "LEFT JOIN members p ON p.id=m.member_id WHERE m.team_id=? ORDER BY m.id DESC LIMIT ?",
                (team_id, limit))[::-1]


def _tok(s):
    return set(re.findall(r"\w+", s.lower()))


def search_scored(team_id, query, k=5):
    """Local retrieval used by the chat (top-k relevant messages instead of dumping everything)."""
    qt = _tok(query)
    rows = _rows(team_id, 500)
    scored = sorted(((len(qt & _tok(r["content"])), r) for r in rows), key=lambda x: -x[0])
    return [r for s, r in scored[:k] if s > 0]


def _post(team_id, member_id, text, source):
    return db.ex("INSERT INTO messages(team_id,member_id,content,source) VALUES(?,?,?,?)", (team_id, member_id, text, source))


async def _mcp_call(team_id, query):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server" / "server.py")], env=dict(os.environ))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("search_team_messages", {"team_id": team_id, "query": query})
            return "\n".join(c.text for c in res.content if hasattr(c, "text"))


def execute(name, args, ctx, guards=True):
    """Run a tool. team_id/member_id always come from ctx (the server), never from model arguments."""
    try:
        if name == "read_team_messages":
            n = max(1, min(int(args.get("limit", 20)), 30))
            out = "\n".join(f"[{r['id']}] {r['who']}: {r['content'][:300]}" for r in _rows(ctx["team_id"], n)) or "(no messages)"
        elif name == "list_my_tasks":
            rows = db.q("SELECT id,title FROM todos WHERE member_id=? AND status='open' ORDER BY id", (ctx["member_id"],))
            out = "\n".join(f"[{r['id']}] {r['title']}" for r in rows) or "(no open tasks)"
        elif name == "search_team_messages":
            out = asyncio.run(_mcp_call(ctx["team_id"], str(args.get("query", ""))))
        elif name == "post_to_team_channel":
            if guards:
                out = "error: posting requires a human approval record"
            else:  # config A only: no approval gate (used to demonstrate the attack)
                _post(ctx["team_id"], ctx["member_id"], str(args.get("text", "")), "agent")
                out = "posted to the team channel"
        else:
            out = f"error: unknown tool {name}"
    except Exception as e:
        out = f"error: {e}"
    return out[:3000]


def post_approved(approval_id):
    """The ONLY guarded way to post. Requires an approval record set by a human via the API."""
    a = db.one("SELECT a.*, r.team_id FROM approvals a JOIN runs r ON r.id=a.run_id WHERE a.id=?", (approval_id,))
    if not a or a["status"] != "approved" or not (a["final_text"] or "").strip():
        raise PermissionError("no human approval record")
    if a["posted"]:
        return "already posted"
    _post(a["team_id"], a["member_id"], a["final_text"], "agent")
    db.ex("UPDATE approvals SET posted=1 WHERE id=?", (approval_id,))
    return "posted to the team channel (human-approved text)"
