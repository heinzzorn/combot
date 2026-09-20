import logging
import os
import re
import subprocess
import sys
import time
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "212-bot"))
import logic  # noqa: E402

import notify  # noqa: E402

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("combot")

# httpx (used internally by python-telegram-bot) logs full request URLs at
# INFO level, and the bot token is embedded directly in the URL -- keep it
# out of the journal entirely rather than relying on redaction alone.
logging.getLogger("httpx").setLevel(logging.WARNING)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def redact(text: str) -> str:
    return text.replace(BOT_TOKEN, "***REDACTED***")

DEPLOYER_TRIGGER = (
    Path(__file__).resolve().parent.parent / "bot-deployer" / "deploy" / "trigger-update.sh"
)


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


@guarded
async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"combot is running. Your chat id is {update.effective_chat.id}."
    )


@guarded
async def ping(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(logic.ping())


@guarded
async def positions(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(logic.positions())


@guarded
async def markets(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(logic.markets())


DEPLOY_TARGETS = ("212-bot", "combot", "all")


@guarded
async def deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = context.args[0] if context.args else "all"
    branch = context.args[1] if len(context.args) > 1 else "main"
    if target not in DEPLOY_TARGETS:
        await update.message.reply_text(
            f"Unknown deploy target: {target} (use 212-bot, combot, or omit for both)"
        )
        return
    try:
        subprocess.run(
            ["sudo", str(DEPLOYER_TRIGGER), target, branch],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as exc:
        await update.message.reply_text(f"Failed to trigger deploy: {redact(exc.stderr)}")
        return
    await update.message.reply_text(f"Deploy triggered for {target}@{branch}, checking now...")


BOT_SERVICE = "212-bot.service"
BOT_ACTIONS = ("start", "stop", "status")


@guarded
async def bot_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.args[0] if context.args else None
    if action not in BOT_ACTIONS:
        await update.message.reply_text("Usage: /bot <start|stop|status>")
        return

    if action == "status":
        result = subprocess.run(
            ["systemctl", "is-active", BOT_SERVICE], capture_output=True, text=True
        )
        await update.message.reply_text(f"{BOT_SERVICE}: {result.stdout.strip()}")
        return

    try:
        subprocess.run(
            ["sudo", "/usr/bin/systemctl", action, BOT_SERVICE],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as exc:
        await update.message.reply_text(f"Failed to {action} {BOT_SERVICE}: {redact(exc.stderr)}")
        return
    await update.message.reply_text(f"OK, {action} issued for {BOT_SERVICE}")


@guarded
async def reboot(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    try:
        subprocess.run(
            ["sudo", "/usr/bin/systemctl", "reboot"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as exc:
        await update.message.reply_text(f"Failed to reboot: {redact(exc.stderr)}")
        return
    await update.message.reply_text("Rebooting now...")


THROTTLE_FLAGS = {
    0: "under-voltage now",
    1: "arm freq capped now",
    2: "throttled now",
    3: "soft temp limit now",
    16: "under-voltage since boot",
    17: "arm freq capped since boot",
    18: "throttled since boot",
    19: "soft temp limit since boot",
}


def _decode_throttled(raw: str) -> str:
    try:
        bits = int(raw.strip().split("=")[1], 16)
    except (IndexError, ValueError):
        return raw
    flags = [label for bit, label in THROTTLE_FLAGS.items() if bits & (1 << bit)]
    return f"0x{bits:x}" + (f" ({', '.join(flags)})" if flags else " (clean)")


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"({exc})"


@guarded
async def sysinfo(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    load1, load5, load15 = Path("/proc/loadavg").read_text().split()[:3]
    temp = _run(["vcgencmd", "measure_temp"]).removeprefix("temp=")
    throttled = _decode_throttled(_run(["vcgencmd", "get_throttled"]))

    lines = [
        f"Uptime: {_run(['uptime', '-p'])}",
        f"Load avg (1/5/15m): {load1} {load5} {load15}",
        f"Temp: {temp}",
        f"Throttled: {throttled}",
        "",
        _run(["free", "-h"]),
        "",
        _run(["df", "-h", "/"]),
    ]
    await update.message.reply_text("\n".join(lines))


LOG_SERVICE = "combot.service"
DEFAULT_LOG_LINES = 20
MAX_LOG_LINES = 100
TELEGRAM_MAX_MESSAGE = 4000


@guarded
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(context.args[0]) if context.args else DEFAULT_LOG_LINES
    except ValueError:
        await update.message.reply_text("Usage: /logs [n]  (n = number of lines, default 20)")
        return
    n = max(1, min(n, MAX_LOG_LINES))

    result = subprocess.run(
        ["sudo", "-n", "/usr/bin/journalctl", "-u", LOG_SERVICE, "-n", str(n), "--no-pager"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        await update.message.reply_text(
            f"journalctl failed (exit {result.returncode}): {redact(result.stderr.strip()) or 'unknown error'}"
        )
        return
    output = redact(result.stdout.strip()) or "(no output)"
    if len(output) > TELEGRAM_MAX_MESSAGE:
        output = "...(truncated)\n" + output[-TELEGRAM_MAX_MESSAGE:]
    await update.message.reply_text(output)


HELP_TEXT = """Available commands:
/start - show this chat's id
/ping - replies pong
/deploy [212-bot|combot] [branch] - check for and apply updates (default: both, main)
/bot <start|stop|status> - control 212-bot.service
/logs [n] - show the last n lines of combot's journal (default 20, max 100)
/sysinfo - uptime, load, temperature, throttling, memory, disk
/reboot - reboot the Pi
/positions - list open Trading212 positions
/markets - list Trading212 exchanges and whether they're currently open
/help - show this message"""


@guarded
async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def post_init(_application: Application):
    if CHAT_ID:
        notify.send("combot started")
    else:
        log.warning("TELEGRAM_CHAT_ID not set; send /start to the bot to discover it")


def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("positions", positions))
    application.add_handler(CommandHandler("markets", markets))
    application.add_handler(CommandHandler("deploy", deploy))
    application.add_handler(CommandHandler("bot", bot_control))
    application.add_handler(CommandHandler("logs", logs))
    application.add_handler(CommandHandler("sysinfo", sysinfo))
    application.add_handler(CommandHandler("reboot", reboot))
    application.add_handler(CommandHandler("help", help_command))

    log.info("combot starting")
    application.run_polling()


if __name__ == "__main__":
    main()
