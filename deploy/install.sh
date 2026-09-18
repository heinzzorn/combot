#!/usr/bin/env bash
set -euo pipefail

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

echo "combot installed and running. Check status with: systemctl status combot.service"
