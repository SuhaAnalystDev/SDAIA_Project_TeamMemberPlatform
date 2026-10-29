"""Minimal MCP server (stdio) exposing one tool: search_team_messages. Read-only access to the SQLite DB."""
import os, re, sqlite3
from pathlib import Path
from mcp.server.fastmcp import FastMCP

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).resolve().parent.parent / "data.db"))
mcp = FastMCP("team-search")


def _tok(s: str) -> set:
    return set(re.findall(r"\w+", s.lower()))


@mcp.tool()
def search_team_messages(team_id: int, query: str, limit: int = 5) -> str:
    """Search a team's recent messages by keyword overlap. Returns the best matches."""
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA query_only=ON")
    rows = c.execute("SELECT m.id, COALESCE(p.name,'?'), m.content FROM messages m "
                     "LEFT JOIN members p ON p.id=m.member_id WHERE m.team_id=? ORDER BY m.id DESC LIMIT 500",
                     (team_id,)).fetchall()
    c.close()
    qt = _tok(query)
    scored = sorted(((len(qt & _tok(r[2])), r) for r in rows), key=lambda x: -x[0])
    out = [f"[{r[0]}] {r[1]}: {r[2][:300]}" for s, r in scored[:max(1, min(limit, 10))] if s > 0]
    return "\n".join(out) or "(no matches)"


if __name__ == "__main__":
    mcp.run()
