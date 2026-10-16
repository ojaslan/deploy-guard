import os
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from groq import Groq
from pydantic import BaseModel

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

router = APIRouter()
DEFAULT_MODEL = "openai/gpt-oss-120b"
_calls = deque()


def _rate_limit():
    """Global limit (protects the Groq quota on a public URL)."""
    limit = int(os.getenv("DG_DIAG_RATE_PER_MIN", "10"))
    now = time.time()
    while _calls and now - _calls[0] > 60:
        _calls.popleft()
    if len(_calls) >= limit:
        raise HTTPException(429, f"Too many diagnosis requests. Limit: {limit} per minute.")
    _calls.append(now)


class DeploymentMetrics(BaseModel):
    error_rate: float
    latency_ms: float
    health_status: str
    source: str | None = None
    requests: int | None = None


@router.post("/diagnose")
def diagnose(metrics: DeploymentMetrics):
    _rate_limit()
    api_key = os.getenv("GROQ_API_KEY", "").strip().strip('"').strip("'")
    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip()
    if not api_key:
        raise HTTPException(500, "GROQ_API_KEY is not set (.env locally, `eb setenv` on AWS).")

    context = ""
    if metrics.source:
        context = f"\n- Data source: {metrics.source}"
        if metrics.requests is not None:
            context += f" ({metrics.requests} requests measured)"
    prompt = f"""You are a senior SRE reviewing a deployment. Metrics:
- Error rate: {metrics.error_rate}%
- Latency (p90): {metrics.latency_ms} ms
- Health status: {metrics.health_status}{context}

Reply in this exact format and keep it short:
VERDICT: <one of OK, INVESTIGATE, ROLLBACK>
Evidence: 2 bullets citing the numbers above.
Likely causes: 2 bullets.
Next steps: 3 numbered steps.
Rollback guidance: 1-2 sentences."""
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )
        text = (completion.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("Model returned empty content")
        return {"diagnosis": text, "model": model}
    except Exception as e:
        print(f"Groq API error: {type(e).__name__}: {e}")
        raise HTTPException(502, f"AI diagnosis failed: {type(e).__name__}: {e}")
