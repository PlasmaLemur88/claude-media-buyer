#!/usr/bin/env python3
"""Read an API key from the environment, then from .env at the engine root. Never prints it.

    from keys import key
    k = key("GEMINI_API_KEY")            # exits with a clear message if missing
    k = key("FAL_KEY", required=False)   # None if missing

Keys this engine uses: FAL_KEY, GEMINI_API_KEY, REPLICATE_API_TOKEN.
Never read a key from another project's folder or from ~/.claude/settings.json.
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def key(name, required=True):
    val = (os.environ.get(name) or "").strip()
    if not val:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith(name + "="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not val and required:
        sys.exit(f"{name} is not set. Put it in the environment or in {ROOT / '.env'} (never commit it).")
    return val or None
