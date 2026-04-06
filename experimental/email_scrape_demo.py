import os
import re
import imaplib
import email
from email.header import decode_header
from email.message import Message

from dotenv import load_dotenv

TARGET_SUBJECT = "Meeting Request: Spells Discussion - Saturday"
SENDER = "thelastdan1@gmail.com"
WIDTH = 64


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


def gmail_thread_id(mail: imaplib.IMAP4_SSL, msg_id: bytes) -> str | None:
    status, data = mail.fetch(msg_id, "(X-GM-THRID)")
    if status != "OK" or not data or not data[0]:
        return None

    raw = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
    match = re.search(r"X-GM-THRID\s+(\d+)", raw)
    return match.group(1) if match else None


if __name__ == "__main__":
    load_dotenv()
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        raise SystemExit("GMAIL_APP_PASSWORD not set")

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(SENDER, password)

    try:
        mail.select("INBOX")
        status, data = mail.search(None, f'SUBJECT "{TARGET_SUBJECT}"')
        if status != "OK" or not data or not data[0]:
            raise SystemExit(f'No email found with subject: "{TARGET_SUBJECT}"')

        original_id = None
        original_msg = None

        for msg_id in data[0].split():
            msg = fetch_message(mail, msg_id)
            if msg and decode_text(msg.get("Subject")).strip() == TARGET_SUBJECT:
                original_id = msg_id
                original_msg = msg
                break

        if not original_id or not original_msg:
            raise SystemExit(f'No email found with exact subject: "{TARGET_SUBJECT}"')

        print_message(original_msg, "ORIGINAL EMAIL")

        thread_id = gmail_thread_id(mail, original_id)
        if not thread_id:
            raise SystemExit("Could not fetch Gmail thread ID")

        mail.select('"[Gmail]/All Mail"')
        status, data = mail.search(None, f"X-GM-THRID {thread_id}")
        if status != "OK" or not data or not data[0]:
            raise SystemExit()

        original_message_id = (original_msg.get("Message-ID") or "").strip()
        replies: dict[str, Message] = {}

        for msg_id in data[0].split():
            msg = fetch_message(mail, msg_id)
            if not msg:
                continue

            message_id = (msg.get("Message-ID") or "").strip() or msg_id.decode()
            if message_id == original_message_id or message_id in replies:
                continue

            replies[message_id] = msg

        for i, msg in enumerate(replies.values(), 1):
            print_message(msg, f"REPLY {i}")

    finally:
        mail.logout()