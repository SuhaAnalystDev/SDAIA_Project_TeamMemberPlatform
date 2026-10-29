import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

APP_NAME = "Team Member"  # English only, never translated
DB_PATH = os.getenv("DB_PATH", str(ROOT / "data.db"))
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
FALLBACKS = [m.strip() for m in os.getenv("OPENROUTER_FALLBACKS", "anthropic/claude-haiku-4.5").split(",") if m.strip()]
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "20"))
DAILY_CAP = int(os.getenv("DAILY_REQUEST_CAP", "50"))
MAX_STEPS = int(os.getenv("MAX_TOOL_STEPS", "6"))
RUN_TOKEN_BUDGET = int(os.getenv("RUN_TOKEN_BUDGET", "20000"))
CHAT_TOKEN_BUDGET = int(os.getenv("CHAT_TOKEN_BUDGET", "3000"))
PRICE_PER_1K = float(os.getenv("PRICE_PER_1K_TOKENS", "0.006"))
