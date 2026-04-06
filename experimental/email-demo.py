import smtplib, ssl, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

sender = "thelastdan1@gmail.com"
receiver = "thelastdan1@gmail.com"
password = os.environ.get("GMAIL_APP_PASSWORD")

msg = MIMEMultipart()
msg["From"] = sender
msg["To"] = receiver
msg["Subject"] = "Hello!"
msg.attach(MIMEText("This is the message body.", "plain"))

context = ssl.create_default_context()
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(sender, password)
    server.sendmail(sender, receiver, msg.as_string())

print("Sent!")