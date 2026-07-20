# Deploying DUKANI POS on an AWS Ubuntu server

This guide takes you from a fresh Ubuntu EC2 instance to a running production
deployment: PostgreSQL + FastAPI backend in Docker, static frontend served by
Nginx, HTTPS via Let's Encrypt.

## 0. Before you start

- An Ubuntu 22.04/24.04 EC2 instance with a public IP (or Elastic IP).
- A domain or subdomain pointed at that IP (an `A` record). You can deploy
  without one and use the raw IP over HTTP, but you won't be able to get a
  free TLS certificate without a domain.
- In the EC2 **Security Group**, inbound rules allowing:
  - `22` (SSH) — ideally restricted to your own IP, not `0.0.0.0/0`
  - `80` (HTTP) and `443` (HTTPS) from anywhere
  - Nothing else needs to be open — Postgres and the backend stay behind Nginx.
- SSH access to the box as a user with `sudo`.

## 1. Server setup

SSH in, then:

```bash
sudo apt update && sudo apt upgrade -y

# Docker + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker   # or log out/in so the group change takes effect

# Nginx + certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Firewall
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 2. Get the code onto the server

```bash
cd /opt
sudo mkdir dukani && sudo chown $USER:$USER dukani
git clone https://github.com/apcoder1204/sales.git dukani
cd dukani
```

## 3. Configure production secrets

Create `/opt/dukani/.env.prod` (used by `docker-compose.prod.yml` — **do not
commit this file**):

```bash
cat > .env.prod <<'EOF'
POSTGRES_DB=dukani_pos
POSTGRES_USER=dukani
POSTGRES_PASSWORD=CHANGE_ME_TO_A_LONG_RANDOM_VALUE
SECRET_KEY=CHANGE_ME_TO_A_DIFFERENT_LONG_RANDOM_VALUE
CORS_ORIGINS=["https://yourdomain.com"]
EOF
```

Generate strong random values instead of typing your own:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # run twice —
                                                                  # once for POSTGRES_PASSWORD,
                                                                  # once for SECRET_KEY
```

`CORS_ORIGINS` must be a JSON array of the exact origin(s) the frontend will
be served from (scheme + host, no trailing slash) — e.g.
`["https://pos.yourdomain.com"]`.

## 4. Start the database + backend

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml ps   # both should be "healthy"/"running"
```

Run migrations and seed the initial roles/branches/users:

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend python -m app.db.seed
```

**Immediately change the seeded default passwords** (every seeded user starts
with password `1234` — see step 8).

The backend is now listening on `127.0.0.1:8000` on the host — not reachable
from the internet yet, which is intentional; Nginx will proxy to it.

## 5. Build and deploy the frontend

The frontend is a static build — no container needed, Nginx serves the files
directly.

```bash
cd /opt/dukani/frontend
cat > .env.production <<'EOF'
VITE_API_BASE_URL=https://yourdomain.com
EOF
# Requires Node.js on the server — easiest via nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 20
npm install
npm run build
```

This produces `/opt/dukani/frontend/dist` — a plain static site.

## 6. Nginx: reverse proxy + static site

```bash
sudo tee /etc/nginx/sites-available/dukani >/dev/null <<'EOF'
server {
    listen 80;
    server_name yourdomain.com;

    # Don't advertise the exact Nginx version in the Server header —
    # trivial to strip, no reason to hand it to anyone fingerprinting for CVEs.
    server_tokens off;

    root /opt/dukani/frontend/dist;
    index index.html;

    # React Router — let the SPA handle unknown paths
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/dukani /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Replace `yourdomain.com` with your real domain first (`sed -i` or edit by
hand). At this point the site should load over plain HTTP.

## 7. HTTPS

```bash
sudo certbot --nginx -d yourdomain.com
```

Certbot edits the Nginx config to add the certificate and redirect HTTP→HTTPS,
and sets up auto-renewal (`systemctl status certbot.timer` to confirm).

Update `frontend/.env.production` and `CORS_ORIGINS` in `.env.prod` to use
`https://` once this is done, then rebuild the frontend
(`npm run build`) if you changed `VITE_API_BASE_URL`.

## 8. Post-deploy checklist — do this before handing the system to real staff

- [ ] Log in as `superadmin` (password `1234`) and change every seeded user's
      password immediately, or deactivate/delete the demo accounts and create
      real ones.
- [ ] Confirm `DEBUG=false` and `ENVIRONMENT=production` (already set in
      `docker-compose.prod.yml`).
- [ ] Confirm `CORS_ORIGINS` is your real domain only — never `["*"]` in
      production.
- [ ] Set up automated Postgres backups, e.g. a nightly cron job:
      `docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U dukani dukani_pos | gzip > /opt/backups/dukani_$(date +%F).sql.gz`
- [ ] Do **not** run `start-demo.sh` / the Cloudflare tunnel on this server —
      that's for local dev demos only.
- [ ] Consider restricting SSH (port 22) in the security group to your own IP.

`server_tokens off` above already strips Nginx's version from the `Server`
header seen by the internet. The backend (gunicorn + uvicorn workers, bound
to `127.0.0.1:8000` only, never reachable directly) sends `Server: uvicorn`
with no version string — that's uvicorn's default, nothing to configure.

## Updating the deployment later

```bash
cd /opt/dukani
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build backend
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
cd frontend && npm install && npm run build
```

## Troubleshooting

- `docker compose -f docker-compose.prod.yml logs -f backend` — backend errors
- `sudo tail -f /var/log/nginx/error.log` — Nginx/proxy errors
- `docker compose -f docker-compose.prod.yml exec postgres psql -U dukani -d dukani_pos` — inspect the database directly
