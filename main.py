import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import auth
import config
import executors
import notify

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("combot")

# httpx (used internally by python-telegram-bot) logs full request URLs at
# INFO level, and the bot token is embedded directly in the URL -- keep it
# out of the journal entirely rather than relying on redaction alone.
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_MAX_MESSAGE = 4000


def _truncate(text: str) -> str:
    if len(text) > TELEGRAM_MAX_MESSAGE:
        return "...(truncated)\n" + text[-TELEGRAM_MAX_MESSAGE:]
    return text


@auth.guarded
async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"combot is running. Your chat id is {update.effective_chat.id}."
    )


@auth.guarded
async def ping(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")


def make_handler(command: config.Command):
    @auth.guarded
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if command.type == "script":
                argv = command.build_argv(context.args)
                result = executors.run_script(
                    command.path, argv, sudo=command.sudo, check=command.check
                )
            elif command.type == "api":
                result = executors.call_api(command.method, command.url, auth=command.auth)
            else:
                result = f"Unknown command type: {command.type}"
        except ValueError as exc:
            result = str(exc)
        await update.message.reply_text(_truncate(result))

    return handler


def build_help_text(commands: list[config.Command]) -> str:
    lines = [
        "Available commands:",
        "/start - show this chat's id",
        "/ping - replies pong",
    ]
    lines += [f"/{cmd.name} - {cmd.description}" for cmd in commands]
    lines.append("/help - show this message")
    return "\n".join(lines)


async def post_init(_application: Application):
    if auth.CHAT_ID:
        notify.send("combot started")
    else:
        log.warning("TELEGRAM_CHAT_ID not set; send /start to the bot to discover it")


def main():
    commands = config.load_commands()
    help_text = build_help_text(commands)

    @auth.guarded
    async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(help_text)

    application = Application.builder().token(auth.BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("help", help_command))
    for command in commands:
        application.add_handler(CommandHandler(command.name, make_handler(command)))

    log.info("combot starting with %d configured commands", len(commands))
    application.run_polling()


if __name__ == "__main__":
    main()
