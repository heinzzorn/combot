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

cat <<EOF | sudo tee /etc/sudoers.d/combot-212bot-control >/dev/null
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/systemctl start 212-bot.service
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/systemctl stop 212-bot.service
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/journalctl -u combot.service *
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/systemctl reboot
EOF
sudo chmod 440 /etc/sudoers.d/combot-212bot-control

sudo systemctl daemon-reload
sudo systemctl enable --now combot.service

echo "combot installed and running. Check status with: systemctl status combot.service"
