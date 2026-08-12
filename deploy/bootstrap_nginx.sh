#!/usr/bin/env bash
# Paste into DigitalOcean Droplet Console (web terminal) as root.
# Fixes Cloudflare 521: nginx on :80 -> uvicorn on :8000
set -euo pipefail

DOMAIN="slava.vevi.monster"

echo "==> Install nginx"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx curl

echo "==> Configure reverse proxy"
cat > /etc/nginx/sites-available/kanban.conf <<'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name slava.vevi.monster;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/kanban.conf /etc/nginx/sites-enabled/kanban.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx

echo "==> Health checks"
curl -s http://127.0.0.1:8000/ && echo ""
curl -s -o /dev/null -w "nginx :80 -> backend: HTTP %{http_code}\n" http://127.0.0.1/

echo ""
echo "Done. In Cloudflare set SSL/TLS mode to Flexible (or Full if you add certbot later)."
echo "Origin should answer on http://${DOMAIN}/"
