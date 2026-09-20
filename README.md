# combot

The Telegram communicator. Owns the bot token and chat, runs the polling
loop, dispatches commands, and sends notifications.

combot's own code has no knowledge of any other project. Every command
beyond a handful of trivial built-ins (`/start`, `/ping`, `/help`) is defined
declaratively in [`commands.yaml`](commands.yaml) as either a script to
execute or an API to call — see `config.py` for the schema and
`executors.py` for how each type actually runs. Adding, removing, or
changing what combot can do is a `commands.yaml` edit, not a code change.

Script paths in `commands.yaml` are resolved relative to this file, and
several point into sibling repos ([212-bot](https://github.com/heinzzorn/212-bot),
[bot-deployer](https://github.com/heinzzorn/bot-deployer)) assuming the
standard sibling-checkout layout — that's a deployment fact recorded in
config, not a code dependency. combot never imports anything from those
repos; it just runs whatever executable `commands.yaml` points at and
relays its stdout.

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

## Adding a command

Add an entry to `commands.yaml`:

```yaml
- name: example
  description: what /help shows for this command
  type: script            # or "api"
  sudo: true               # prefixes `sudo -n`; omit if not needed
  check: true               # false if a non-zero exit isn't a real failure
  path: ../some-repo/scripts/example
  argv: ["{arg_one}"]
  args:
    - name: arg_one
      choices: ["a", "b"]   # or: pattern (regex), or: type: int with min/max
      default: "a"
```

`args` entries map positionally to what's typed after the command in
Telegram (`/example foo` → `arg_one=foo`); each is validated before
substitution into `argv`, so a Telegram user can never inject anything
beyond a declared, validated value. `type: api` commands take `method`,
`url`, and an optional `auth` block (`basic`/`bearer`/`header`, values
pulled from combot's own env vars) instead of `path`/`argv`/`sudo`.

Nothing in `main.py`, `config.py`, or `executors.py` needs to change for a
new command — only `commands.yaml`, and whatever script/API it points at.

## Standalone install

Normally this is set up by [bot-deployer](https://github.com/heinzzorn/bot-deployer),
which clones this repo alongside `212-bot` and runs the install below. To set
up combot on its own:

```
./deploy/install.sh
```

This creates a venv, installs dependencies, creates `.env` from `.env.example`
if missing, installs/starts `combot.service` (systemd, `Restart=always`,
starts on boot), and installs the sudoers rule needed for the `sudo: true`
commands in `commands.yaml`.

Check status:

```
systemctl status combot.service
journalctl -u combot.service -f
```
