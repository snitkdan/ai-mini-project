#!/usr/bin/env python3
"""Temporal activities: call Gemini API and persist result to SQLite."""

import os
import uuid

from braintrust import init_logger
from braintrust.integrations.langchain import BraintrustCallbackHandler
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from temporalio import activity

from storage.client import DBClient


# Worker-local registry: connection_id → DBClient instance
_DB_REGISTRY: dict[str, DBClient] = {}


@activity.defn
async def open_db_connection() -> str:
    """Open a DBClient, register it locally, and return its connection id."""
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
    load_dotenv()
    init_logger(project="ai-mini-project", api_key=os.environ.get("BRAINTRUST_API_KEY"))

    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a friendly assistant."),
            ("human", "{prompt}"),
        ]
    )
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

    parser = StrOutputParser()
    chain = chat_prompt | llm | parser

    config = RunnableConfig(callbacks=[BraintrustCallbackHandler()])
    return chain.invoke({"prompt": prompt}, config=config)


@activity.defn
async def save_to_db(conn_id: str, prompt: str, response: str) -> int:
    """Persist prompt + response using an existing connection, return new row id."""
    db = _DB_REGISTRY.get(conn_id)
    if db is None:
        msg = f"No DB connection found for id: {conn_id}"
        raise RuntimeError(msg)
    return db.insert(prompt=prompt, response=response)
