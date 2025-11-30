"""
Utility script to export FastAPI OpenAPI schema to docs/openapi.json.

Usage:
    cd backend
    source venv/bin/activate  # optional, ensure deps installed
    python scripts/generate_openapi.py
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parent
for candidate in (REPO_ROOT, BASE_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

for env_file in (REPO_ROOT / ".env", BASE_DIR / ".env"):
    if env_file.exists():
        load_dotenv(env_file, override=False)

from app.main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    output = BASE_DIR.parent / "docs" / "openapi.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2))
    print(f"OpenAPI schema written to {output}")


if __name__ == "__main__":
    main()
