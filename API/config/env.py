"""Tiny zero-dependency .env loader (shared-hosting friendly — no python-dotenv).

Call ``load_dotenv()`` at the top of settings.py. Existing OS environment
variables always win over file values, so cPanel "Environment Variables"
or Apache SetEnv directives are never overridden by a stale .env file.
"""
import os
from pathlib import Path


def load_dotenv(stream=None):
    """Parse KEY=VALUE lines and inject them into os.environ (no overwrite)."""
    if stream is None:
        path = Path(__file__).resolve().parent.parent.parent / ".env"  # project root
        if not path.is_file():
            return False
        stream = path.open("r", encoding="utf-8")
        with stream as fh:
            _parse(fh)
        return True
    with stream as fh:
        _parse(fh)
    return True


def _parse(fh):
    for line in fh:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # strip inline comment only when value isn't quoted
        if value[:1] in ("'", '"'):
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        elif " #" in value:
            value = value.split(" #", 1)[0].strip()
        if key and key not in os.environ:
            os.environ[key] = value
