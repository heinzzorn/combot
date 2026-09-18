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


async def trigger_update(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    try:
        subprocess.run(
            ["sudo", str(DEPLOYER_TRIGGER)],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as exc:
        await update.message.reply_text(f"Failed to trigger update: {exc.stderr}")
        return
    await update.message.reply_text("Update triggered, checking now...")


async def post_init(_application: Application):
    if CHAT_ID:
        notify.send("combot started")
    else:
        log.warning("TELEGRAM_CHAT_ID not set; send /start to the bot to discover it")


def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("update", trigger_update))

    log.info("combot starting")
    application.run_polling()


if __name__ == "__main__":
    main()
