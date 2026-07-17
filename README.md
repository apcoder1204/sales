# DUKANI POS

A point-of-sale and inventory management system for a multi-branch retail business (built for a CCTV/security equipment retailer in Tanzania). Swahili UI with an English toggle.

## Stack

- **Backend**: FastAPI + async SQLAlchemy (asyncpg) + PostgreSQL 16
- **Frontend**: React 18 + Vite

## Features

- Role-based access (super admin, admin, general manager, store keeper, cashier)
- Point of sale with cash / mobile money / bank transfer payments
- Multi-product stock requests between branches with partial-fulfillment approval
- Direct branch-to-branch stock transfers
- End-of-day cash closing with variance reconciliation ("matumizi" / expense entries)
- Sales, inventory, branch, cashier, and closing reports — PDF/Excel export
- Full audit log

## Local development

See [`backend/README`](backend) setup below and `frontend/.env` for the dev API URL. Quick start:

```bash
# Database
sudo -u postgres bash setup_db.sh

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit SECRET_KEY etc.
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Or with Docker Compose for local dev: `docker compose up --build`.

## Production deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for a full guide to deploying on an AWS Ubuntu server (Docker Compose + Nginx + Let's Encrypt).

## Demo/tunnel mode

`./start-demo.sh` exposes the local dev server through a Cloudflare Tunnel for quick remote demos. `./stop-demo.sh` tears it down. **Not for production use.**
