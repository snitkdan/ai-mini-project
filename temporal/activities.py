import os
import requests
from temporalio import activity
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
URL = (
    f"https://generativelanguage.googleapis.com"
    f"/v1beta/models/{MODEL}:generateContent"
)

@activity.defn
async def say_hello(name: str) -> str:
    prompt = name
    print(f"Processing prompt: {prompt}")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
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
    return data["candidates"][0]["content"]["parts"][0]["text"]