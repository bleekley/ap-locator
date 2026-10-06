"""Shared config: loads secrets from .env and the controller list from controllers.csv."""
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"

load_dotenv(ROOT / ".env")


def creds(kind: str = "WLC") -> dict:
    """Return username/password/secret for 'WLC' or 'SWITCH' from the environment.

    SWITCH falls back to WLC creds if the SWITCH_* vars are blank.
    """
    user = os.getenv(f"{kind}_USERNAME") or os.getenv("WLC_USERNAME")
    pw = os.getenv(f"{kind}_PASSWORD") or os.getenv("WLC_PASSWORD")
    en = os.getenv(f"{kind}_ENABLE") or os.getenv("WLC_ENABLE") or pw
    if not user or not pw or user == "changeme":
        sys.exit(
            "Missing credentials. Copy .env.example to .env and fill in "
            f"{kind}_USERNAME / {kind}_PASSWORD. Never commit .env."
        )
    return {"username": user, "password": pw, "secret": en}


def creds_for(name: str, kind: str = "WLC") -> dict:
    """Per-controller override: CRED_<NAME>_USERNAME / _PASSWORD / _ENABLE in .env
    (name uppercased, dashes to underscores). Falls back to the global creds."""
    key = name.upper().replace("-", "_")
    user = os.getenv(f"CRED_{key}_USERNAME")
    pw = os.getenv(f"CRED_{key}_PASSWORD")
    if user and pw:
        return {
            "username": user,
            "password": pw,
            "secret": os.getenv(f"CRED_{key}_ENABLE") or pw,
        }
    return creds(kind)


def controllers(path: Path | None = None) -> list[dict]:
    """Read controllers.csv: name,host,type  (type = 9800 or aireos)."""
    path = path or ROOT / "controllers.csv"
    if not path.exists():
        sys.exit(f"Controller list not found: {path}. See controllers.example.csv.")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not {"name", "host", "type"}.issubset(reader.fieldnames or []):
            sys.exit("Controller list requires name,host,type headers.")
        rows = []
        names, hosts = set(), set()
        for line, raw in enumerate(reader, 2):
            if None in raw:
                sys.exit(f"Controller list row {line}: too many fields.")
            r = {k: (v or "").strip() for k, v in raw.items()}
            if not all(r[k] for k in ("name", "host", "type")):
                sys.exit(f"Controller list row {line}: name, host and type are required.")
            r["type"] = r["type"].lower()
            if r["type"] not in ("9800", "aireos"):
                sys.exit(f"Controller list row {line}: type must be 9800 or aireos.")
            if r["name"].lower() in names or r["host"].lower() in hosts:
                sys.exit(f"Controller list row {line}: duplicate controller name or host.")
            names.add(r["name"].lower())
            hosts.add(r["host"].lower())
            rows.append({k: r[k] for k in ("name", "host", "type")})
    if not rows:
        sys.exit("Controller list is empty; inventory was not changed.")
    return rows
