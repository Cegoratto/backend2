#!/usr/bin/env bash
# Run from your machine after SSH access is configured:
#   ssh second-project 'bash -s' < deploy/setup_server.sh
# Or on the server:
#   cd /opt/kanban-backend && git pull && systemctl restart kanban-backend
set -euo pipefail

APP_DIR="/opt/kanban-backend"
cd "$APP_DIR"

git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
systemctl restart kanban-backend
systemctl restart nginx

echo "Deployed. Health:"
curl -s http://127.0.0.1:8000/
echo ""
curl -s -o /dev/null -w "nginx: HTTP %{http_code}\n" http://127.0.0.1/
