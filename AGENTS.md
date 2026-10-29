# AGENTS.md: Team Member agent contract

Platform name: **Team Member** (English only, never translated).

## Role
A team-workspace assistant. It summarizes team messages, plans a user's day from their open tasks, and drafts team announcements. Chat agents (summarize, email drafting, priority planning, plus manager-created ones) answer only within their one job and reply in the user's language.

## Tools
| Tool | Used by | Notes |
|---|---|---|
| `read_team_messages` | summary, announcement | read-only, current team only |
| `list_my_tasks` | planning, announcement | read-only, current user only |
| `search_team_messages` | summary, announcement | served over MCP (`mcp_server/server.py`, read-only DB) |
| `post_to_team_channel` | announcement only | external action; never executes from the model in config B |

`team_id` and `member_id` come from server context, never from model arguments.

## Rules (enforced in code, not in the prompt)
1. Least privilege: each task kind gets only its allowlisted tools (`tools.KIND_TOOLS`); other calls return an error.
2. `post_to_team_channel` pauses the run and creates an `approvals` row. Only the run owner, via `POST /api/runs/{id}/decision`, can approve (and may edit the text). `tools.post_approved` raises `PermissionError` without an approved record.
3. Team messages and task text are untrusted data: wrapped in `<untrusted_data>` (defence in depth only; the gate is the defence).
4. The API key is read only from the `OPENROUTER_API_KEY` env var, backend only. Never commit `.env`.
5. Every UI string lives in `static/i18n.js` in both languages.

## Limits
- Max tool steps per run: 6 (`MAX_TOOL_STEPS`); token budget per run: 20,000 (`RUN_TOKEN_BUDGET`).
- Daily cap: 50 requests per member (`DAILY_REQUEST_CAP`).
- LLM timeout 20 s, then fallback models (`OPENROUTER_FALLBACKS`); if all fail the run stops with `llm_error`.
- Chat memory is compacted above `CHAT_TOKEN_BUDGET` (3,000 est. tokens), keeping the last 6 turns.
- Exit reasons are explicit: `done`, `max_steps`, `budget_exhausted`, `llm_error`, `approval_denied`.
- Config A (baseline, no guards) exists only for evals and the attack demo.
