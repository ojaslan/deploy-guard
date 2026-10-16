import os


def region():
    """Region from env, else None so boto3 resolves it (config, or the EC2 instance itself)."""
    return (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip() or None
