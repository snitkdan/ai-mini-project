#!/usr/bin/env python3

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY")

MODEL = "gemini-2.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

prompt = " ".join(sys.argv[1:]).strip()
if not prompt:
    raise SystemExit("Usage: python gemini_cli.py 'your prompt here'")

payload = {
    "contents": [
        {
            "parts": [
                {"text": prompt}
            ]
        }
    ]
}

resp = requests.post(
    URL,
    headers={
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY,
    },
    json=payload,
    timeout=60,
)

resp.raise_for_status()
data = resp.json()
print(data["candidates"][0]["content"]["parts"][0]["text"])