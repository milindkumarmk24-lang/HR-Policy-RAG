"""List the Gemini models your API key can call (pick one for GEMINI_MODEL).

    python scripts/list_models.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google import genai  # noqa: E402

from app.config import get_settings  # noqa: E402

settings = get_settings()
if not settings.has_api_key:
    raise SystemExit("GOOGLE_API_KEY is not set. Add it to backend/.env first.")
client = genai.Client(api_key=settings.google_api_key)
print(f"Configured: GEMINI_MODEL={settings.gemini_model}\n")
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or []
    if "generateContent" in actions:
        print(m.name.removeprefix("models/"))
