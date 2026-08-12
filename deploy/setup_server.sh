#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/kanban-backend"
REPO_URL="${REPO_URL:-https://github.com/Cegoratto/backend2.git}"

echo "==> Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx curl

echo "==> Cloning/updating backend"
if [ -d "$APP_DIR/.git" ]; then
  cd "$APP_DIR"
  git pull --ff-only
else
  rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
  cd "$APP_DIR"
fi

echo "==> Python venv + dependencies"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

mkdir -p data

if [ ! -f .env ]; then
  cp deploy/.env.production.example .env
  echo "!! Created $APP_DIR/.env from example — edit secrets before going live"
fi

echo "==> systemd service"
cp deploy/systemd/kanban-backend.service /etc/systemd/system/kanban-backend.service
systemctl daemon-reload
systemctl enable kanban-backend
systemctl restart kanban-backend

echo "==> nginx"
cp deploy/nginx/kanban.conf /etc/nginx/sites-available/kanban.conf
ln -sf /etc/nginx/sites-available/kanban.conf /etc/nginx/sites-enabled/kanban.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx

echo "==> Done. Backend:"
systemctl --no-pager status kanban-backend | head -5
curl -s http://127.0.0.1:8000/ || true
echo ""
curl -s -o /dev/null -w "nginx -> backend: HTTP %{http_code}\n" http://127.0.0.1/
