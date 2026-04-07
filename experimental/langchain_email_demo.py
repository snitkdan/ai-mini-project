import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.callbacks.base import BaseCallbackHandler
from braintrust import init_logger
from braintrust.integrations.langchain import BraintrustCallbackHandler


class StepLogger(BaseCallbackHandler):
    def on_chain_start(self, serialized, inputs, run_id, parent_run_id, **kwargs):
        name = (serialized or {}).get("name", None)
        if name is None:
            name = "RunnableSequence" if parent_run_id is None else "StrOutputParser"
        print(f"[START] {name} → inputs: {inputs}")

    def on_chain_end(self, outputs, run_id, parent_run_id, **kwargs):
        name = "RunnableSequence" if parent_run_id is None else "StrOutputParser"
        print(f"[END]   {name} → outputs: {outputs}")

    def on_llm_start(self, serialized, prompts, **kwargs):
        name = (serialized or {}).get("name", "Unknown")
        print(f"[LLM START] {name} → sending {len(prompts)} message(s) to Gemini")

    def on_llm_end(self, response, **kwargs):
        print(f"[LLM END]   received response from Gemini ✓")

    def on_llm_error(self, error, **kwargs):
        print(f"[LLM ERROR] ✗ {error}")

    def on_chain_error(self, error, **kwargs):
        print(f"[CHAIN ERROR] ✗ {error}")


# Prompt for generating a subject line from the email body
subject_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Generate a concise, professional email subject line for the given message body. Return only the subject line, no extra text.",
        ),
        ("human", "Email body:\n{email_body}"),
    ]
)

parser = StrOutputParser()


def send_email(sender: str, receiver: str, password: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    print(f'\n✅ Email sent to {receiver} with subject: "{subject}"')


if __name__ == "__main__":
    load_dotenv()

    init_logger(project="ai-mini-project", api_key=os.environ.get("BRAINTRUST_API_KEY"))

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    subject_chain = subject_prompt | llm | parser

    logger = StepLogger()
    bt_handler = BraintrustCallbackHandler()

    # Step 1: Ask user for their email message
    print("Assistant: What would you like your email message to say?")
    email_body = input("You: ").strip()

    if not email_body:
        print("No message provided. Exiting.")
        exit(1)

    # Step 2: Use LLM to generate a subject line
    print("\nGenerating subject line...")
    subject = subject_chain.invoke(
        {"email_body": email_body},
        config={"callbacks": [logger, bt_handler]},
    )
    print(f"\nGenerated subject: {subject}")

    # Step 3: Send the email
    sender = "thelastdan1@gmail.com"
    receiver = "thelastdan1@gmail.com"
    password = os.environ.get("GMAIL_APP_PASSWORD")

    if not password:
        print("❌ GMAIL_APP_PASSWORD not set in environment.")
        exit(1)

    send_email(sender, receiver, password, subject, email_body)
    print("Sent email!")
