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
anyone else gets "Not authorized." Every command attempt (with its content)
is logged via Python's `logging`, which under `combot.service` lands in the
journal — see it with `journalctl -u combot.service`. Logged content is
sanitized first: control/escape characters are stripped (so a message can't
inject fake log lines or terminal escape sequences into your journal) and
capped at 200 characters. Only *unauthorized* attempts also get reported to
your chat (via `notify.py`), and only with who they are (user id, username,
chat id) — never the command content, which stays in the journal — and at
most once per minute per user, so repeated attempts can't spam your chat.
Before `TELEGRAM_CHAT_ID` is set, there's no owner to check against yet, so
commands run unrestricted — this is what lets the very first `/start` work to
discover your chat id.

## Controlling 212-bot

```
/bot start    # sudo systemctl start 212-bot.service
/bot stop     # sudo systemctl stop 212-bot.service
/bot status   # systemctl is-active 212-bot.service
```

Requires the sudoers rule installed by `deploy/install.sh` (see below).

## Viewing logs

```
/logs        # last 20 lines of combot's journal
/logs 100    # last 100 lines (max)
```

Runs `sudo journalctl -u combot.service`, requiring the same sudoers rule as
above.

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
`212-bot.service` and read its own journal.

Check status:

```
systemctl status combot.service
journalctl -u combot.service -f
```
