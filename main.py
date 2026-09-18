import logging
import os
import subprocess
import sys
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

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

DEPLOYER_TRIGGER = (
    Path(__file__).resolve().parent.parent / "bot-deployer" / "deploy" / "trigger-update.sh"
)


async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"combot is running. Your chat id is {update.effective_chat.id}."
    )


async def ping(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(logic.ping())


DEPLOY_TARGETS = ("212-bot", "combot", "all")


async def deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = context.args[0] if context.args else "all"
    if target not in DEPLOY_TARGETS:
        await update.message.reply_text(
            f"Unknown deploy target: {target} (use 212-bot, combot, or omit for both)"
        )
        return
    try:
        subprocess.run(
            ["sudo", str(DEPLOYER_TRIGGER), target],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as exc:
        await update.message.reply_text(f"Failed to trigger deploy: {exc.stderr}")
        return
    await update.message.reply_text(f"Deploy triggered for {target}, checking now...")


BOT_SERVICE = "212-bot.service"
BOT_ACTIONS = ("start", "stop", "status")


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
        await update.message.reply_text(f"Failed to {action} {BOT_SERVICE}: {exc.stderr}")
        return
    await update.message.reply_text(f"OK, {action} issued for {BOT_SERVICE}")


HELP_TEXT = """Available commands:
/start - show this chat's id
/ping - replies pong
/deploy [212-bot|combot] - check for and apply updates (default: both)
/bot <start|stop|status> - control 212-bot.service
/help - show this message"""


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
    application.add_handler(CommandHandler("deploy", deploy))
    application.add_handler(CommandHandler("bot", bot_control))
    application.add_handler(CommandHandler("help", help_command))

    log.info("combot starting")
    application.run_polling()


if __name__ == "__main__":
    main()
