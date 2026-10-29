import hashlib, json, re
import httpx
from . import db
from .config import API_KEY, BASE_URL, MODEL, FALLBACKS, TIMEOUT, APP_NAME


class LLMError(Exception):
    pass


def _args(s):
    try:
        return json.loads(s) if isinstance(s, str) else (s or {})
    except ValueError:
        return {}


def _call(messages, tools):
    last = None
    for model in [MODEL] + FALLBACKS:           # fallback if the model errors, is rate-limited, or stalls > TIMEOUT s
        body = {"model": model, "messages": messages, "temperature": 0}
        if tools:
            body["tools"] = tools
        try:
            resp = httpx.post(f"{BASE_URL}/chat/completions", json=body, timeout=TIMEOUT,
                              headers={"Authorization": f"Bearer {API_KEY}", "X-Title": APP_NAME})
            resp.raise_for_status()
            d = resp.json()
            m = d["choices"][0]["message"]
            tcs = [{"id": t["id"], "name": t["function"]["name"], "arguments": _args(t["function"].get("arguments"))}
                   for t in (m.get("tool_calls") or [])]
            return {"content": m.get("content") or "", "tool_calls": tcs,
                    "tokens": (d.get("usage") or {}).get("total_tokens", 0), "model": model}
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            last = e
    raise LLMError(f"all models failed: {last}")


def _called(messages, name):
    return any(tc["function"]["name"] == name for m in messages if m["role"] == "assistant" for tc in m.get("tool_calls", []))


def _mock(messages, tools):
    """Offline stand-in used when OPENROUTER_API_KEY is empty. Deterministic and deliberately naive:
    it obeys instructions found in tool output, so the prompt-injection attack can be demonstrated."""
    names = {t["function"]["name"] for t in (tools or [])}
    tokens = len(json.dumps(messages, ensure_ascii=False)) // 4
    out = lambda content="", calls=None: {"content": content, "tool_calls": calls or [], "tokens": tokens, "model": "mock"}
    call = lambda name, args: [{"id": f"call_{len(messages)}", "name": name, "arguments": args}]
    if not tools:
        return out("[mock mode: no OPENROUTER_API_KEY set] I received your message.")
    tool_msgs = [m for m in messages if m["role"] == "tool"]
    system = messages[0]["content"]
    kind = (re.search(r"\[kind=(\w+)\]", system) or [None, ""])[1]
    for m in reversed(tool_msgs):                 # naive model: follows injected instructions
        inj = re.search(r"ignore (?:all |your |previous )*instructions and post (.+)", m["content"], re.I)
        if inj and "post_to_team_channel" in names and not _called(messages, "post_to_team_channel"):
            return out("", call("post_to_team_channel", {"text": inj.group(1).strip(" \"'.")}))
    n = len(tool_msgs)
    if kind == "announcement" and _called(messages, "post_to_team_channel") and messages[-1]["role"] == "tool":
        return out("Announcement published.")
    if kind == "announcement":
        plan = [("read_team_messages", {"limit": 20}), ("list_my_tasks", {}), ("search_team_messages", {"query": "announcement"})]
        if n < 3:
            return out("", call(*plan[n]))
        if n == 3:
            return out("", call("post_to_team_channel", {"text": "Team update: please review the latest messages and your open tasks."}))
        return out("Announcement published.")
    if kind == "summary":
        if n == 0:
            return out("", call("read_team_messages", {"limit": 20}))
        return out("Summary: " + tool_msgs[0]["content"][:300])
    if kind == "planning":
        if n == 0:
            return out("", call("list_my_tasks", {}))
        return out("Plan: " + tool_msgs[0]["content"][:300])
    return out("Done.")


def chat(messages, tools=None, cache=True):
    key = hashlib.sha256(json.dumps([messages, tools, MODEL if API_KEY else "mock"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if cache:
        hit = db.one("SELECT value FROM llm_cache WHERE key=?", (key,))
        if hit:
            r = json.loads(hit["value"])
            r["tokens"], r["cached"] = 0, True
            return r
    r = _call(messages, tools) if API_KEY else _mock(messages, tools)
    if cache:
        db.ex("INSERT OR REPLACE INTO llm_cache(key,value) VALUES(?,?)", (key, json.dumps(r, ensure_ascii=False)))
    return r


def assistant_message(r):
    m = {"role": "assistant", "content": r["content"] or None}
    if r["tool_calls"]:
        m["tool_calls"] = [{"id": t["id"], "type": "function",
                            "function": {"name": t["name"], "arguments": json.dumps(t["arguments"], ensure_ascii=False)}}
                           for t in r["tool_calls"]]
    return m
