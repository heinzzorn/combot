#!/usr/bin/env python3
import os
import sys
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send(text: str) -> None:
    if not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    urllib.request.urlopen(url, data=data, timeout=10)


if __name__ == "__main__":
    send(" ".join(sys.argv[1:]))
