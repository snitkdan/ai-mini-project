#!/usr/bin/env python3
"""Temporal activities: call Gemini API and persist result to SQLite."""

import os
import uuid
from datetime import timedelta

import httpx
from dotenv import load_dotenv
from temporalio import activity

load_dotenv()

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL: str = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/gemini-2.5-flash:generateContent"
)

# Worker-local registry: connection_id → DBClient instance
_DB_REGISTRY: dict[str, "DBClient"] = {}


@activity.defn
async def open_db_connection() -> str:
    """Open a DBClient, register it locally, and return its connection id."""
    from storage.client import DBClient

    conn_id = str(uuid.uuid4())
    _DB_REGISTRY[conn_id] = DBClient()
    return conn_id


@activity.defn
async def close_db_connection(conn_id: str) -> None:
    """Close and deregister the DBClient associated with conn_id."""
    db = _DB_REGISTRY.pop(conn_id, None)
    if db is not None:
        db.close()


@activity.defn
async def call_gemini(prompt: str) -> str:
    """POST prompt to the Gemini API and return the text response."""
    params: dict[str, str] = {"key": GEMINI_API_KEY}
    payload: dict = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(GEMINI_URL, params=params, json=payload)
        resp.raise_for_status()

    data: dict = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


@activity.defn
async def save_to_db(conn_id: str, prompt: str, response: str) -> int:
    """Persist prompt + response using an existing connection, return new row id."""
    db = _DB_REGISTRY.get(conn_id)
    if db is None:
        raise RuntimeError(f"No DB connection found for id: {conn_id}")
    return db.insert(prompt=prompt, response=response)