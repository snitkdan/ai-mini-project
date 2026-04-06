import os
import re
import imaplib
import email
import smtplib
import ssl
from email.header import decode_header
from email.message import Message
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.callbacks.base import BaseCallbackHandler
from braintrust import init_logger
from braintrust.integrations.langchain import BraintrustCallbackHandler


SENDER = "thelastdan1@gmail.com"
WIDTH = 64

refine_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a professional email assistant. "
        "Rewrite the user's draft reply to be more professional and concise. "
        "Return only the rewritten email body, no extra commentary.",
    ),
    ("human", "{draft_reply}"),
])


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


# ── IMAP helpers ──────────────────────────────────────────────────────────────

def decode_text(value: str | None) -> str:
    if not value:
        return ""
    return "".join(
        part.decode(charset or "utf-8", errors="replace")
        if isinstance(part, bytes)
        else part
        for part, charset in decode_header(value)
    )


def plain_body(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if (
                part.get_content_type() == "text/plain"
                and "attachment"
                not in str(part.get("Content-Disposition", "")).lower()
            ):
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
    elif msg.get_content_type() == "text/plain":
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return "[No plain-text body found]"


def fetch_message(mail: imaplib.IMAP4_SSL, msg_id: bytes) -> Message | None:
    status, data = mail.fetch(msg_id, "(RFC822)")
    if status != "OK" or not data or not data[0]:
        return None
    return email.message_from_bytes(data[0][1])


def gmail_thread_id(mail: imaplib.IMAP4_SSL, msg_id: bytes) -> str | None:
    status, data = mail.fetch(msg_id, "(X-GM-THRID)")
    if status != "OK" or not data or not data[0]:
        return None
    raw = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
    match = re.search(r"X-GM-THRID\s+(\d+)", raw)
    return match.group(1) if match else None


def msg_datetime(msg: Message):
    date_str = msg.get("Date")
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        from datetime import datetime, timezone
        return datetime.min.replace(tzinfo=timezone.utc)


# ── Print helpers ─────────────────────────────────────────────────────────────

def print_rule(char: str = "─") -> None:
    print(char * WIDTH)


def print_message(msg: Message, label: str) -> None:
    print_rule("═")
    print(f"  {label}")
    print_rule("═")
    print(f"  From     :  {decode_text(msg.get('From'))}")
    print(f"  To       :  {decode_text(msg.get('To'))}")
    if msg.get("Cc"):
        print(f"  Cc       :  {decode_text(msg.get('Cc'))}")
    print(f"  Date     :  {decode_text(msg.get('Date'))}")
    print(f"  Subject  :  {decode_text(msg.get('Subject'))}")
    print_rule()
    print("  BODY")
    print_rule()
    for line in plain_body(msg).strip().splitlines():
        print(f"  {line}")
    print_rule("═")
    print()


# ── SMTP helper ───────────────────────────────────────────────────────────────

def send_reply(
    sender: str,
    receiver: str,
    password: str,
    subject: str,
    body: str,
    in_reply_to: str,
    references: str,
):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg["In-Reply-To"] = in_reply_to
    msg["References"] = references
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    print(f"\n✅ Reply sent to {receiver} with subject: \"{subject}\"")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    load_dotenv()

    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        raise SystemExit("❌ GMAIL_APP_PASSWORD not set")

    init_logger(
        project="ai-mini-project",
        api_key=os.environ.get("BRAINTRUST_API_KEY"),
    )

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    refine_chain = refine_prompt | llm | StrOutputParser()
    logger = StepLogger()
    bt_handler = BraintrustCallbackHandler()

    # ── Step 1: Get subject from user and find the thread ─────────────────────
    target_subject = input("Enter the exact email subject to search for:\n> ").strip()
    if not target_subject:
        raise SystemExit("❌ No subject provided.")

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(SENDER, password)

    try:
        mail.select("INBOX")
        status, data = mail.search(None, f'SUBJECT "{target_subject}"')
        if status != "OK" or not data or not data[0]:
            raise SystemExit(f'❌ No email found with subject: "{target_subject}"')

        original_id = None
        original_msg = None

        for msg_id in data[0].split():
            msg = fetch_message(mail, msg_id)
            if msg and decode_text(msg.get("Subject")).strip() == target_subject:
                original_id = msg_id
                original_msg = msg
                break

        if not original_id or not original_msg:
            raise SystemExit(
                f'❌ No email found with exact subject: "{target_subject}"'
            )

        thread_id = gmail_thread_id(mail, original_id)
        if not thread_id:
            raise SystemExit("❌ Could not fetch Gmail thread ID")

        mail.select('"[Gmail]/All Mail"')
        status, data = mail.search(None, f"X-GM-THRID {thread_id}")
        if status != "OK" or not data or not data[0]:
            raise SystemExit("❌ Could not fetch thread messages")

        # Collect all messages in thread, sort by date, pick latest
        thread_messages: list[Message] = []
        for msg_id in data[0].split():
            msg = fetch_message(mail, msg_id)
            if msg:
                thread_messages.append(msg)

        if not thread_messages:
            raise SystemExit("❌ Thread appears to be empty")

        thread_messages.sort(key=msg_datetime)
        latest_msg = thread_messages[-1]

        # ── Step 2: Show the latest reply and prompt for a draft ──────────────
        print_message(latest_msg, "LATEST MESSAGE IN THREAD")

        print("Assistant: How would you like to reply to this email?")
        draft = input("You: ").strip()
        if not draft:
            raise SystemExit("❌ No reply provided.")

        # ── Step 3: Refine with LLM and send ──────────────────────────────────
        print("\nRefining your reply...")
        refined = refine_chain.invoke(
            {"draft_reply": draft},
            config={"callbacks": [logger, bt_handler]},
        )

        final_body = f"[AGENT-REPLY]\n\n{refined}"

        print_rule("═")
        print("  REFINED REPLY PREVIEW")
        print_rule("═")
        for line in final_body.splitlines():
            print(f"  {line}")
        print_rule("═")

        confirm = input("\nSend this reply? (y/n): ").strip().lower()
        if confirm != "y":
            raise SystemExit("Aborted — reply not sent.")

        original_sender = decode_text(original_msg.get("From"))
        reply_subject = f"Re: {target_subject}"
        in_reply_to = (latest_msg.get("Message-ID") or "").strip()
        existing_refs = (latest_msg.get("References") or "").strip()
        references = (
            f"{existing_refs} {in_reply_to}".strip() if existing_refs else in_reply_to
        )

        send_reply(
            sender=SENDER,
            receiver=original_sender,
            password=password,
            subject=reply_subject,
            body=final_body,
            in_reply_to=in_reply_to,
            references=references,
        )

    finally:
        mail.logout()