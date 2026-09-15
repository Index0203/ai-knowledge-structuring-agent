# Deployment

This document describes how to run the stack, what the production configuration
does, and what to change before other people use it.

## 1. Prerequisites

- Docker Desktop (Windows/macOS) or Docker Engine with Compose v2 (Linux)
- About 2 GB of free memory and 3 GB of disk space for the first image build
- No local Node.js or Python installation is required — both runtimes live in the images

## 2. Run it

### Production stack (single machine)

```powershell
.\scripts\deploy.ps1          # Windows
```

If Windows blocks the script ("running scripts is disabled on this system"),
either double-click `scripts\deploy.cmd` or run
`powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1`.

```sh
sh scripts/deploy.sh          # macOS / Linux
```

The script creates `.env` from `.env.example` when it is missing, builds the
images, starts every service, applies database migrations, waits for the backend
health check and then prints the addresses. Run it again after pulling changes —
it rebuilds and restarts without touching the data volumes.

The same thing by hand:

```sh
cp .env.example .env                                  # Windows: Copy-Item .env.example .env
docker compose -f docker-compose.prod.yml up -d --build
```

Then open the web app at `http://localhost:3000` and the API docs at
`http://localhost:8000/docs`.

### Development stack

```powershell
Copy-Item .env.example .env
.\scripts\start.ps1
```

The development compose file bind-mounts the source, so uvicorn and Next.js
reload on change. Celery workers do not reload: run
`docker compose restart worker` after changing task, agent or service code.

## 3. What the production stack does

| Area | Behaviour |
| --- | --- |
| Images | Backend and frontend are multi-stage with `dev` and `prod` targets; the production images bake the source in, nothing is bind-mounted |
| Backend | Uvicorn with `UVICORN_WORKERS` processes (default 2), running as an unprivileged user (uid 10001) |
| Frontend | Next.js standalone output served by `node server.js`, also unprivileged |
| Database | A one-shot `migrate` service runs `alembic upgrade head` before the API and workers start |
| Health checks | Backend `/health`, frontend `/`, PostgreSQL (`pg_isready`) and Redis (`redis-cli ping`); the API waits for migrations, the web app waits for a healthy API |
| Restarts | Every long-running service uses `restart: unless-stopped` |
| Ports | Only the API and the web app publish ports (`BACKEND_PORT`, `FRONTEND_PORT`); PostgreSQL, Redis, ChromaDB and MinIO stay on the internal network |
| Data | Named volumes: `postgres_data`, `redis_data`, `chroma_data`, `minio_data`, `backend_upload_data` |

## 4. Environment variables

Copy `.env.example` to `.env` and edit what you need. The file is ignored by git.

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_ENV` | Environment name reported by the app | `development` |
| `NEXT_PUBLIC_API_BASE_URL` | API address used by the browser. It is inlined when the frontend image is built, so changing it requires rebuilding that image | `http://localhost:8000` |
| `BACKEND_CORS_ORIGINS` | Comma-separated origins allowed to call the API | `http://localhost:3000` |
| `BACKEND_PORT` / `FRONTEND_PORT` | Host ports for the API and the web app | `8000` / `3000` |
| `UVICORN_WORKERS` | API worker processes in the production image | `2` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials. Changing the password also requires updating `DATABASE_URL` | `knowledge_agent` / `app` / `app` |
| `DATABASE_URL` | SQLAlchemy connection string used by the backend and Alembic | points at the `postgres` service |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | Object storage credentials | `minioadmin` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` | Chat model provider. Leave empty to run in degraded mode (structure from the document outline, extractive answers) | empty |
| `EMBEDDING_PROVIDER` | `deterministic` keeps retrieval working without an API key | `deterministic` |
| `OCR_*`, retrieval and retry variables | Pipeline tuning; the defaults are fine for most documents | see `.env.example` |

## 5. Before other people use it

- [ ] Set `APP_ENV=production`
- [ ] Change `POSTGRES_PASSWORD` **and** the matching password inside `DATABASE_URL`
- [ ] Change `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`
- [ ] Point `BACKEND_CORS_ORIGINS` at the real web origin
- [ ] Point `NEXT_PUBLIC_API_BASE_URL` at the address browsers will use, then rebuild the frontend image
- [ ] Provide a model key, or confirm the degraded mode is acceptable
- [ ] Keep PostgreSQL, Redis, ChromaDB and MinIO off the public network
- [ ] Schedule backups of the named volumes
- [ ] Add authentication: the API currently accepts any caller that knows a document id
      (see `项目现状与待改进清单.docx` / `docs/HANDOVER.md` §10)

## 6. Operations

```sh
# status and logs
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend worker

# rebuild and restart after a code change
docker compose -f docker-compose.prod.yml up -d --build

# re-run migrations on demand
docker compose -f docker-compose.prod.yml run --rm migrate

# stop (keeps every volume)
docker compose -f docker-compose.prod.yml down

# database backup and restore
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U app knowledge_agent > backup.sql
cat backup.sql | docker compose -f docker-compose.prod.yml exec -T postgres psql -U app -d knowledge_agent
```

## 7. Troubleshooting

| Symptom | Check |
| --- | --- |
| A port is already in use | Change `BACKEND_PORT` / `FRONTEND_PORT` in `.env`, or stop whatever holds the port |
| The API never becomes healthy | `docker compose -f docker-compose.prod.yml logs migrate backend` — usually a credential mismatch between `POSTGRES_*` and `DATABASE_URL` |
| The page loads but requests fail | `NEXT_PUBLIC_API_BASE_URL` must be reachable from the browser (it is baked in at build time), and `BACKEND_CORS_ORIGINS` must include the web origin |
| Model calls fail | Verify `OPENAI_API_KEY`, `OPENAI_MODEL` and `OPENAI_BASE_URL`; the stack still runs without them in degraded mode |
| Documents stay in "processing" | `docker compose -f docker-compose.prod.yml logs worker beat` |
