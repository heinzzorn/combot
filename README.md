# combot

The Telegram communicator. Owns the bot token and chat, runs the polling
loop, dispatches commands, and sends notifications.

Business logic lives in the sibling [212-bot](https://github.com/heinzzorn/212-bot)
repo. Synchronous functions (e.g. `logic.ping()`) are imported directly via a
relative sys.path entry — this repo must be checked out next to a `212-bot`
checkout (both under the same parent directory) for that import to work.
212-bot also runs as its own standalone service (`212-bot.service`), which
`/bot start`, `/bot stop`, and `/bot status` control independently of combot.

`/deploy`, `/deploy 212-bot`, `/deploy combot`, or `/deploy combot my-branch`
trigger [bot-deployer](https://github.com/heinzzorn/bot-deployer) (also
expected as a sibling checkout) to check for and apply updates to one or both
repos, from `main` or another branch, on demand — see its README for how
that's kept safe despite combot restarting itself as part of the update.

## Telegram setup

1. Talk to [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`, and copy the token it gives you.
2. Set `TELEGRAM_BOT_TOKEN=<that token>` in `.env` (see below).
3. Start combot, then send it `/start` from your phone. It replies with your chat id.
4. Put that chat id into `.env` as `TELEGRAM_CHAT_ID=<id>` and restart (`sudo systemctl restart combot.service`) so it can message you proactively, not just reply to commands.

`.env` is not committed to git (see `.gitignore`) since it holds the bot token — treat that token like a password.

## Access control

Once `TELEGRAM_CHAT_ID` is set, every command is restricted to that user id —
anyone else gets "Not authorized." Every command attempt, from you or anyone
else, is also reported back to your chat (via `notify.py`) so you always see
who's poking the bot, even in chats you're not part of. Before
`TELEGRAM_CHAT_ID` is set, there's no owner to check against yet, so commands
run unrestricted — this is what lets the very first `/start` work to
discover your chat id.

## Controlling 212-bot

```
/bot start    # sudo systemctl start 212-bot.service
/bot stop     # sudo systemctl stop 212-bot.service
/bot status   # systemctl is-active 212-bot.service
```

Requires the sudoers rule installed by `deploy/install.sh` (see below).

## Standalone install

Normally this is set up by [bot-deployer](https://github.com/heinzzorn/bot-deployer),
which clones this repo alongside `212-bot` and runs the install below. To set
up combot on its own (with `../212-bot` already checked out):

```
./deploy/install.sh
```

This creates a venv, installs dependencies, creates `.env` from `.env.example`
if missing, installs/starts `combot.service` (systemd, `Restart=always`,
starts on boot), and installs the sudoers rule combot needs to start/stop
`212-bot.service`.

Check status:

```
systemctl status combot.service
journalctl -u combot.service -f
```
