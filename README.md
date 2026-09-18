# combot

The Telegram communicator. Owns the bot token and chat, runs the polling
loop, dispatches commands, and sends notifications.

Business logic lives in the sibling [212-bot](https://github.com/heinzzorn/212-bot)
repo, imported directly (`import logic`) via a relative sys.path entry — this
repo must be checked out next to a `212-bot` checkout (both under the same
parent directory) for that import to work.

## Telegram setup

1. Talk to [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`, and copy the token it gives you.
2. Set `TELEGRAM_BOT_TOKEN=<that token>` in `.env` (see below).
3. Start combot, then send it `/start` from your phone. It replies with your chat id.
4. Put that chat id into `.env` as `TELEGRAM_CHAT_ID=<id>` and restart (`sudo systemctl restart combot.service`) so it can message you proactively, not just reply to commands.

`.env` is not committed to git (see `.gitignore`) since it holds the bot token — treat that token like a password.

## Standalone install

Normally this is set up by [bot-deployer](https://github.com/heinzzorn/bot-deployer),
which clones this repo alongside `212-bot` and runs the install below. To set
up combot on its own (with `../212-bot` already checked out):

```
./deploy/install.sh
```

This creates a venv, installs dependencies, creates `.env` from `.env.example`
if missing, and installs/starts `combot.service` (systemd, `Restart=always`,
starts on boot).

Check status:

```
systemctl status combot.service
journalctl -u combot.service -f
```
