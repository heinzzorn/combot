#!/usr/bin/env bash
set -euo pipefail

# Standalone/dev install: creates a venv, installs deps, and starts
# combot.service under whatever user runs this script.
#
# For the production Pi setup (dedicated `combot` system user, secrets in
# /etc/combot/combot.env, sudoers rules), use bot-deployer's
# deploy/install.sh + deploy/provision-services.sh instead -- this script no
# longer installs sudoers rules itself, to avoid two sources of truth for
# them drifting apart.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="$(whoami)"

cd "$REPO_DIR"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example -- set TELEGRAM_BOT_TOKEN in it before combot can start"
fi

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

sed -e "s#__REPO_DIR__#$REPO_DIR#g" -e "s#__USER__#$SERVICE_USER#g" \
    deploy/combot.service | sudo tee /etc/systemd/system/combot.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now combot.service

echo "combot installed and running as $SERVICE_USER. Check status with: systemctl status combot.service"
echo "Note: this standalone install has no sudoers rules, so /bot, /deploy, /logs, and /reboot"
echo "won't work until you add them yourself (see bot-deployer's provision-services.sh) or run"
echo "the production install via bot-deployer instead."
