#!/usr/bin/env python3
"""Temporal activities: call Gemini API and persist result to SQLite."""

import os
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


@activity.defn
async def call_gemini(prompt: str) -> str:
    """POST prompt to the Gemini API and return the text response."""
    params: dict[str, str] = {"key": GEMINI_API_KEY}
    payload: dict = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(GEMINI_URL, params=params, json=payload)
        resp.raise_for_status()

    data: dict = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


@activity.defn
async def save_to_db(prompt: str, response: str, close_db: bool) -> int:
    """Persist prompt + response to the transactions table, return new row id."""
    from storage.client import DBClient

    db = DBClient()
    row_id: int = db.insert(prompt=prompt, response=response)
    if close_db:
        db.close()
    return row_id