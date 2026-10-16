import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.awsutil import region

MAX_RECORDS = 100


def _path() -> Path:
    default = Path(__file__).resolve().parent / "deployment_history.json"
    return Path(os.getenv("DG_HISTORY_PATH", str(default)))


def _table():
    """DynamoDB table when DG_DDB_TABLE is set, otherwise None (local JSON file)."""
    name = os.getenv("DG_DDB_TABLE", "").strip()
    if not name:
        return None
    import boto3

    return boto3.resource("dynamodb", region_name=region()).Table(name)


def _load_file() -> list:
    p = _path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def load_history() -> list:
    """Oldest to newest, at most MAX_RECORDS."""
    table = _table()
    if table is None:
        return _load_file()
    try:
        from boto3.dynamodb.conditions import Key

        resp = table.query(
            KeyConditionExpression=Key("pk").eq("history"),
            ScanIndexForward=False,
            Limit=MAX_RECORDS,
        )
        return [json.loads(i["data"]) for i in reversed(resp.get("Items", []))]
    except Exception as e:  # never break the API because storage is down
        print(f"DynamoDB read failed: {type(e).__name__}: {e}")
        return []


def save_analysis(record: dict) -> None:
    stamp = datetime.now(UTC)
    record = {**record, "timestamp": stamp.isoformat(timespec="seconds")}
    table = _table()
    if table is not None:
        try:
            table.put_item(Item={
                "pk": "history",
                "ts": stamp.strftime("%Y-%m-%dT%H:%M:%S.%f") + "#" + uuid.uuid4().hex[:6],
                "data": json.dumps(record),
            })
        except Exception as e:
            print(f"DynamoDB write failed: {type(e).__name__}: {e}")
        return
    history = (_load_file() + [record])[-MAX_RECORDS:]
    try:
        _path().write_text(json.dumps(history, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"History write skipped: {e}")
