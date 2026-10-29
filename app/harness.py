"""Rules enforced in code (not in prompts): budgets, caps, run configurations."""
from dataclasses import dataclass
from datetime import date
from . import db
from .config import DAILY_CAP, MAX_STEPS, RUN_TOKEN_BUDGET, PRICE_PER_1K


class CapExceeded(Exception):
    pass


@dataclass(frozen=True)
class Config:
    name: str
    guards: bool       # allowlist + approval gate + untrusted-data wrapping + budgets
    max_steps: int
    token_budget: int
    cache: bool = True


A = Config("A", False, 20, 10**9)                       # baseline: plain prompt, no guards
B = Config("B", True, MAX_STEPS, RUN_TOKEN_BUDGET)      # full harness
CONFIGS = {"A": A, "B": B}


def cost(tokens: int) -> float:
    return round(tokens / 1000 * PRICE_PER_1K, 6)


def check_and_count(member_id: int):
    day = date.today().isoformat()
    db.ex("INSERT OR IGNORE INTO usage(member_id,day,n) VALUES(?,?,0)", (member_id, day))
    n = db.one("SELECT n FROM usage WHERE member_id=? AND day=?", (member_id, day))["n"]
    if n >= DAILY_CAP:
        raise CapExceeded(f"daily request cap ({DAILY_CAP}) reached")
    db.ex("UPDATE usage SET n=n+1 WHERE member_id=? AND day=?", (member_id, day))


def log_chat(user, agent_name, tokens):
    db.ex("INSERT INTO runs(team_id,member_id,kind,title,status,exit_reason,config,tokens,cost) VALUES(?,?,?,?,?,?,?,?,?)",
          (user["team_id"], user["id"], "chat", agent_name, "done", "done", "B", tokens, cost(tokens)))
