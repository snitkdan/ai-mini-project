#!/usr/bin/env python3
"""Temporal activities: call Gemini API and persist result to SQLite."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from temporalio import activity

from storage.client import DBClient


if TYPE_CHECKING:
    from workflow.observability import ObservabilityDeps


class Activities:
    def __init__(self, observability: ObservabilityDeps) -> None:
        self.observability = observability
        self.db_registry: dict[str, DBClient] = {}

    @activity.defn
    def open_db_connection(self) -> str:
        conn_id = str(uuid.uuid4())
        self.db_registry[conn_id] = DBClient()
        return conn_id

    @activity.defn
    def close_db_connection(self, conn_id: str) -> None:
        db = self.db_registry.pop(conn_id, None)
        if db is not None:
            db.close()

    @activity.defn
    def call_gemini(self, prompt: str) -> str:
        load_dotenv()
        self.observability.init()

        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        agent = create_agent(
            model=llm,
            tools=[],
            system_prompt="You are a friendly assistant.",
        )

        callback = self.observability.make_callback_handler()
        callbacks = [callback] if callback is not None else []
        config = RunnableConfig(callbacks=callbacks)

        result: dict[str, list[BaseMessage]] = agent.invoke(
            {"messages": [HumanMessage(content=prompt)]},
            config=config,
        )

        content = result["messages"][-1].content
        if not isinstance(content, str):
            err = f"Expected str content from LLM, got {type(content)}"
            raise TypeError(err)
        return content

    @activity.defn
    def save_to_db(self, conn_id: str, prompt: str, response: str) -> int:
        db = self.db_registry.get(conn_id)
        if db is None:
            err = f"No DB connection found for id: {conn_id}"
            raise RuntimeError(err)
        return db.insert(prompt=prompt, response=response)
