# Load environment variables (e.g., GOOGLE_API_KEY, BRAINTRUST_API_KEY) from a .env file
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.callbacks.base import BaseCallbackHandler
from braintrust import init_logger
from braintrust.integrations.langchain import BraintrustCallbackHandler

# Custom callback handler that hooks into LangChain's event system to log
# each stage of the chain's execution as it happens
class StepLogger(BaseCallbackHandler):

    # Fires when any chain (or sub-chain) begins — infers its name since
    # LangChain doesn't always populate `serialized` reliably
    def on_chain_start(self, serialized, inputs, run_id, parent_run_id, **kwargs):
        name = (serialized or {}).get("name", None)
        if name is None:
            # No parent_run_id means this is the root RunnableSequence;
            # otherwise it's a nested component like the parser
            name = "RunnableSequence" if parent_run_id is None else "StrOutputParser"
        print(f"[START] {name} → inputs: {inputs}")

    # Fires when a chain finishes, using the same parent-check heuristic to name it
    def on_chain_end(self, outputs, run_id, parent_run_id, **kwargs):
        name = "RunnableSequence" if parent_run_id is None else "StrOutputParser"
        print(f"[END]   {name} → outputs: {outputs}")

    # Fires just before the LLM API call is made, reporting how many messages are sent
    def on_llm_start(self, serialized, prompts, **kwargs):
        name = (serialized or {}).get("name", "Unknown")
        print(f"[LLM START] {name} → sending {len(prompts)} message(s) to Gemini")

    # Fires after the LLM returns a successful response
    def on_llm_end(self, response, **kwargs):
        print(f"[LLM END]   received response from Gemini ✓")

    # Fires if the LLM call throws an error, surfacing it immediately
    def on_llm_error(self, error, **kwargs):
        print(f"[LLM ERROR] ✗ {error}")

    # Fires if any chain step throws an error (e.g., prompt formatting failure)
    def on_chain_error(self, error, **kwargs):
        print(f"[CHAIN ERROR] ✗ {error}")

# Define the prompt template that injects user input into a fixed system+human
# message structure before sending to the LLM
#
#   ┌─────────────────────────────────────┐
#   │  system: "You are a friendly..."    │
#   │  human:  "{user_input}"  ◄── filled │
#   │           at invoke time            │
#   └─────────────────────────────────────┘
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a friendly assistant."),
    ("human", "{user_input}"),
])

# Parser that strips the raw AIMessage wrapper and returns a plain Python string
parser = StrOutputParser()

if __name__ == "__main__":
    load_dotenv()

    # Initialize Braintrust logger — traces will appear under this project in the UI
    init_logger(project="ai-mini-project", api_key=os.environ.get("BRAINTRUST_API_KEY"))

    # Instantiate the Gemini model client that will handle the actual API call
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

    # Compose the three components into a single pipeline using LangChain's pipe
    # operator — data flows left to right through each stage:
    #
    #   {"user_input": ...}
    #         │
    #         ▼
    #   ┌───────────┐    ┌─────┐    ┌────────┐
    #   │  prompt   │───►│ llm │───►│ parser │───► str
    #   └───────────┘    └─────┘    └────────┘
    chain = prompt | llm | parser

    # Instantiate both callbacks:
    #   - StepLogger: prints each stage to stdout for local debugging
    #   - BraintrustCallbackHandler: ships traces to the Braintrust UI
    logger = StepLogger()
    bt_handler = BraintrustCallbackHandler()

    # Collect input from the user at the terminal, then run it through the full
    # chain with both callbacks attached so every stage is printed and traced
    # ... all your existing setup code (prompt, llm, parser, StepLogger, etc.) ...
    user_input = input("You: ")
    response = chain.invoke(
        {"user_input": user_input},
        config={"callbacks": [logger, bt_handler]},
    )

    print(f"\nGemini: {response}")