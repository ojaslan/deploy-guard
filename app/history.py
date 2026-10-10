import json
import os
from datetime import datetime, timezone
from pathlib import Path

MAX_RECORDS = 100


def _path() -> Path:
    default = Path(__file__).resolve().parent / "deployment_history.json"
    return Path(os.getenv("DG_HISTORY_PATH", str(default)))


def load_history() -> list:
    p = _path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_analysis(record: dict) -> None:
    """Dev-only storage. Never crash the API if the disk is read-only."""
    record = {**record, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    history = load_history()
    history.append(record)
    history = history[-MAX_RECORDS:]
    try:
        _path().write_text(json.dumps(history, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"History write skipped: {e}")
