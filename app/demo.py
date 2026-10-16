"""Incident Lab: a fault-injectable demo route so telemetry measures REAL damage.

The fault is confined to /demo/work and reverts by itself after MODE_TTL seconds.
"""
import asyncio
import random
import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/demo", tags=["demo"])
MODE_TTL = 120
_state = {"mode": "healthy", "until": 0.0}


def current_mode() -> str:
    if _state["mode"] != "healthy" and time.time() > _state["until"]:
        _state["mode"] = "healthy"
    return _state["mode"]


class ModeBody(BaseModel):
    mode: Literal["healthy", "slow", "failing"]


@router.post("/mode")
def set_mode(body: ModeBody):
    _state["mode"] = body.mode
    _state["until"] = time.time() + MODE_TTL
    return {"mode": body.mode, "reverts_in_seconds": 0 if body.mode == "healthy" else MODE_TTL}


@router.get("/mode")
def get_mode():
    return {"mode": current_mode()}


@router.get("/work")
async def work():
    mode = current_mode()
    if mode == "slow":
        await asyncio.sleep(random.uniform(0.6, 1.2))
    elif mode == "failing":
        if random.random() < 0.7:
            raise HTTPException(500, "simulated failure")
        await asyncio.sleep(random.uniform(0.05, 0.2))
    else:
        await asyncio.sleep(random.uniform(0.01, 0.08))
    return {"ok": True, "mode": mode}
