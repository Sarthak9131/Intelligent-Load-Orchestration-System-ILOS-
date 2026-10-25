"""
Application settings loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM ───────────────────────────────────────────────────────────────────────
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6")
MAX_AGENT_ATTEMPTS = 2
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── Processing ────────────────────────────────────────────────────────────────
MAX_CONCURRENT_APPLICATIONS = int(os.getenv("MAX_CONCURRENT_APPLICATIONS", "10"))
PROCESSING_TIMEOUT_SECONDS = int(os.getenv("PROCESSING_TIMEOUT_SECONDS", "120"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
AUDIT_DIR = os.getenv("AUDIT_DIR", "audit")

# ── Risk thresholds ───────────────────────────────────────────────────────────
APPROVE_THRESHOLD = float(os.getenv("APPROVE_THRESHOLD", "30"))
CONDITIONAL_THRESHOLD = float(os.getenv("CONDITIONAL_THRESHOLD", "60"))
MAX_DTI_RATIO = float(os.getenv("MAX_DTI_RATIO", "0.43"))
MAX_LTI_RATIO = float(os.getenv("MAX_LTI_RATIO", "5.0"))
