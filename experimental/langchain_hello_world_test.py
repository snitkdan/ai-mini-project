# test_chain.py
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_hello_world import prompt, parser

# ── Chain integration tests (LLM mocked) ───────────────────────────────────


class TestChainIntegration:
    """Test the full chain with the LLM call mocked out."""

    def test_chain_returns_string(self):
        """Chain should return a plain string, not an AIMessage."""
        fake_llm = RunnableLambda(lambda _: AIMessage(content="Hello there!"))

        chain = prompt | fake_llm | parser
        result = chain.invoke({"user_input": "Hi"})

        assert isinstance(result, str)
        assert result == "Hello there!"

    def test_chain_passes_user_input(self):
        """Verify the user input reaches the LLM."""
        received: list = []

        def capture(prompt_value):
            received.append(prompt_value)
            return AIMessage(content="pong")

        fake_llm = RunnableLambda(capture)
        chain = prompt | fake_llm | parser
        chain.invoke({"user_input": "ping"})

        human_msg = received[0].to_messages()[-1]
        assert "ping" in human_msg.content


# ── Prompt template tests ───────────────────────────────────────────────────


class TestPromptTemplate:
    def test_prompt_formats_correctly(self):
        messages = prompt.format_messages(user_input="Tell me a joke")
        assert len(messages) == 2
        assert messages[0].content == "You are a friendly assistant."
        assert messages[1].content == "Tell me a joke"
