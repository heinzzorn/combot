import logging
import os
import re
import time
from functools import wraps

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes

import notify

load_dotenv()

log = logging.getLogger("combot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def redact(text: str) -> str:
    return text.replace(BOT_TOKEN, "***REDACTED***")


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
MAX_LOGGED_LENGTH = 200


def sanitize(text: str) -> str:
    """Strips control/escape characters (log injection, terminal escapes) and
    caps length, before untrusted message content ever reaches the log."""
    text = " ".join(_CONTROL_CHARS.sub(" ", text).split())
    if len(text) > MAX_LOGGED_LENGTH:
        text = text[:MAX_LOGGED_LENGTH] + "...(truncated)"
    return text


_last_unauthorized_notify: dict[int, float] = {}
UNAUTHORIZED_NOTIFY_COOLDOWN = 60  # seconds


def _should_notify_unauthorized(user_id: int) -> bool:
    now = time.monotonic()
    if now - _last_unauthorized_notify.get(user_id, 0) < UNAUTHORIZED_NOTIFY_COOLDOWN:
        return False
    _last_unauthorized_notify[user_id] = now
    return True


def guarded(handler):
    """Logs every command attempt (with content) to the journal, and rejects
    anyone whose user id isn't CHAT_ID (the owner) -- reporting only who they
    are to the owner's chat (rate-limited per user), never the command
    content. Before CHAT_ID is configured there's no owner to check against
    yet, so commands go through unrestricted -- this is what lets /start work
    during initial setup."""

    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat_id = update.effective_chat.id
        text = sanitize(update.message.text or "")

        log.info("user %s (@%s) in chat %s: %s", user.id, user.username, chat_id, text)

        if CHAT_ID and str(user.id) != str(CHAT_ID):
            if _should_notify_unauthorized(user.id):
                notify.send(f"unauthorized activity: user {user.id} (@{user.username}) in chat {chat_id}")
            await update.message.reply_text("Not authorized.")
            return

        await handler(update, context)

    return wrapped
