"""Per-user, per-agent conversation memory with a token budget and compaction."""
from . import db, llm
from .config import CHAT_TOKEN_BUDGET

KEEP_LAST = 6


def est(s: str) -> int:
    return max(1, len(s) // 4)


def add(member_id, agent_id, role, content):
    db.ex("INSERT INTO conversations(member_id,agent_id,role,content) VALUES(?,?,?,?)", (member_id, agent_id, role, content))


def history(member_id, agent_id):
    return db.q("SELECT id,role,content FROM conversations WHERE member_id=? AND agent_id=? ORDER BY id", (member_id, agent_id))


def build(member_id, agent_id):
    rows = history(member_id, agent_id)
    if sum(est(r["content"]) for r in rows) > CHAT_TOKEN_BUDGET and len(rows) > KEEP_LAST:
        old, keep = rows[:-KEEP_LAST], rows[-KEEP_LAST:]
        text = "\n".join(f"{r['role']}: {r['content']}" for r in old)
        try:
            summary = llm.chat([{"role": "system", "content": "Summarize this conversation briefly. Keep facts and decisions. "
                                 "Use the same language as the conversation."}, {"role": "user", "content": text}], cache=False)["content"]
        except llm.LLMError:
            summary = text[-1500:]  # fallback: truncate instead of failing
        db.ex("DELETE FROM conversations WHERE id IN (%s)" % ",".join(str(r["id"]) for r in old))
        db.ex("INSERT INTO conversations(member_id,agent_id,role,content) VALUES(?,?,?,?)", (member_id, agent_id, "summary", summary))
        rows = history(member_id, agent_id)
    return [{"role": "system", "content": "Summary of earlier conversation: " + r["content"]} if r["role"] == "summary"
            else {"role": r["role"], "content": r["content"]} for r in rows]
