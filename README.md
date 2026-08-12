# Kanban Backend (FastAPI)

Python-бэкенд для Kanban-приложения. Заменяет Supabase (auth + CRUD) и Cloudflare Worker (AI).

Подробная документация миграции: [`second_project/docs/REST_MIGRATION.md`](../second_project/docs/REST_MIGRATION.md)

## Стек

- FastAPI
- SQLAlchemy 2.x (async)
- JWT auth (email/password + Google OAuth)
- OpenRouter для AI
- SQLite (dev) или PostgreSQL (prod)

## Быстрый старт

### 1. Установить зависимости

```powershell
cd backend2
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настроить окружение

```powershell
copy .env.example .env
```

По умолчанию используется SQLite (не нужен PostgreSQL):

```env
DATABASE_URL=sqlite+aiosqlite:///./data/kanban.db
OPENROUTER_API_KEY=sk-or-...   # из backend/.dev.vars
JWT_SECRET=случайная-длинная-строка
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
```

`GOOGLE_CLIENT_ID` — Web Client ID из Google Cloud Console (тот же, что `VITE_GOOGLE_CLIENT_ID` на фронтенде). Client Secret не нужен.

Для PostgreSQL замените `DATABASE_URL` и выполните `alembic upgrade head`.

### 3. Запуск

```powershell
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000  
Документация: http://localhost:8000/docs

Таблицы SQLite создаются автоматически при старте.

### 4. Тестовые пользователи

```powershell
.\.venv\Scripts\python.exe scripts\seed_users.py
```

Создаёт 10 пользователей с разными ролями. Пароль: `password123`.

| Email | Роль |
|-------|------|
| alexey@example.com | Frontend Developer |
| maria@example.com | Backend Developer |
| ivan@example.com | Fullstack Developer |
| olga@example.com | Mobile Developer |
| dmitry@example.com | QA Engineer |
| elena@example.com | DevOps Engineer |
| anna@example.com | UI/UX Designer |
| sergey@example.com | Product Manager |
| natalia@example.com | Team Lead |
| pavel@example.com | Project Manager |

Повторный запуск пропускает уже существующих пользователей.

## Тесты

```powershell
pytest
```

Тесты используют SQLite в памяти.

## API

### Auth

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/auth/register` | Регистрация |
| POST | `/api/auth/login` | Вход по email/password |
| POST | `/api/auth/google` | Вход через Google (`{ "idToken": "..." }`) |
| GET | `/api/auth/me` | Текущий пользователь |

### Profiles

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/profiles` | Список пользователей |
| PATCH | `/api/profiles/me` | Обновить teamRole |

### Boards / Columns / Cards

| Метод | Путь |
|-------|------|
| GET | `/api/boards` |
| GET | `/api/boards/{boardId}` |
| POST | `/api/boards` |
| DELETE | `/api/boards/{boardId}` |
| GET | `/api/boards/{boardId}/members` |
| POST | `/api/boards/{boardId}/columns` |
| DELETE | `/api/columns/{columnId}` |
| POST | `/api/columns/{columnId}/cards` |
| PATCH | `/api/cards/{cardId}` |
| DELETE | `/api/cards/{cardId}` |
| POST | `/api/cards/{cardId}/move` |

### AI

| Метод | Путь |
|-------|------|
| POST | `/api/ask` |
| POST | `/api/tasks/decompose-and-assign` |

### Billing (Stripe)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/billing/plans` | Список тарифов |
| GET | `/api/billing/subscription` | Текущая подписка |
| POST | `/api/billing/checkout` | Создать Stripe Checkout Session |
| POST | `/api/billing/subscribe` | Переход на Free (отмена подписки) |
| GET | `/api/billing/payments` | История платежей |
| POST | `/api/billing/webhook` | Webhook Stripe (без JWT) |

Все защищённые эндпоинты требуют `Authorization: Bearer <token>`.

## Stripe

Добавьте в `.env`:

```env
FRONTEND_URL=http://localhost:5173
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_TEAM=price_...
```

### Webhook (production)

1. Stripe Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://slava.vevi.monster/api/billing/webhook`
3. События: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`
4. Скопируйте Signing secret в `STRIPE_WEBHOOK_SECRET`

### Локальная разработка

```powershell
# Терминал 1 — бэкенд (рекомендуется порт 8001, если на 8000 остались старые процессы)
cd backend2
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001

# Терминал 2 — фронтенд
cd second_project
npm run dev:local
```

Фронтенд в режиме `dev:local` обращается к `VITE_API_BASE_URL` из `.env.dev-local` (по умолчанию `http://127.0.0.1:8001`).

Webhook для локального бэкенда на порту 8001:

```powershell
stripe listen --forward-to localhost:8001/api/billing/webhook
```

CLI выдаст временный `whsec_...` для `.env`.

Тестовая карта: `4242 4242 4242 4242`.

## Подключение фронтенда

Фронтенд (`second_project`) уже мигрирован на REST API.

```powershell
# Терминал 1
cd backend2 && uvicorn app.main:app --reload --port 8000

# Терминал 2
cd second_project && npm run dev
```

Альтернатива без Vite proxy: задайте `VITE_API_BASE_URL=http://127.0.0.1:8001` в `second_project/.env.dev-local`.

## Деплой на DigitalOcean (slava.vevi.monster)

Дроплет: `165.227.147.62` (SSH host: `second-project` в `~/.ssh/config`).

Бэкенд уже отвечает на `http://165.227.147.62:8000`. Если `https://slava.vevi.monster` отдаёт **521** — Cloudflare не достучался до origin на порту 80. Нужен nginx как reverse proxy.

### Быстрый фикс (через консоль DigitalOcean)

1. [DigitalOcean](https://cloud.digitalocean.com/) → Droplets → ваш дроплет → **Access** → **Launch Droplet Console**
2. Войдите как `root`
3. Выполните:

```bash
curl -fsSL https://raw.githubusercontent.com/Cegoratto/backend2/main/deploy/bootstrap_nginx.sh | bash
```

Или скопируйте содержимое `deploy/bootstrap_nginx.sh` вручную.

4. В **Cloudflare** → SSL/TLS → режим **Flexible** (или **Full** после certbot)

### Полный деплой (через SSH)

```powershell
# На дроплете (первый раз)
ssh second-project
curl -fsSL https://raw.githubusercontent.com/Cegoratto/backend2/main/deploy/setup_server.sh | bash
nano /opt/kanban-backend/.env   # секреты из локального .env
systemctl restart kanban-backend
```

Скопируйте в `/opt/kanban-backend/.env` на сервере:

- `JWT_SECRET`, `OPENROUTER_API_KEY`, `GOOGLE_CLIENT_ID`
- Stripe-переменные
- `CORS_ORIGINS` — добавьте URL фронтенда (например `https://your-app.pages.dev`)
- `FRONTEND_URL` — публичный URL фронтенда

Обновление после `git push`:

```bash
ssh second-project 'cd /opt/kanban-backend && git pull && .venv/bin/pip install -r requirements.txt && systemctl restart kanban-backend'
```

### SSH-доступ

Если `Permission denied (publickey)` — добавьте свой публичный ключ в DigitalOcean → Droplet → **Settings** → **Security** → **Add SSH Key**, или вставьте ключ в `/root/.ssh/authorized_keys` через веб-консоль.

## PostgreSQL (опционально)

1. Установить PostgreSQL: https://www.postgresql.org/download/windows/
2. Создать БД: `psql -U postgres -c "CREATE DATABASE kanban;"`
3. В `.env`: `DATABASE_URL=postgresql+asyncpg://postgres:ПАРОЛЬ@localhost:5432/kanban`
4. `alembic upgrade head`

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `scripts/seed_users.py` | 10 тестовых пользователей |
| `scripts/setup_db.bat` | Создание БД kanban (PostgreSQL) |
| `scripts/create_database.sql` | SQL для создания БД |
| `deploy/setup_server.sh` | Первичная настройка дроплета |
| `deploy/bootstrap_nginx.sh` | Только nginx → :8000 (фикс Cloudflare 521) |
| `deploy/deploy.sh` | Обновление после git pull |

## Устранение проблем

| Ошибка | Решение |
|--------|---------|
| `connection refused` :5432 | Используйте SQLite или запустите PostgreSQL |
| `database "kanban" does not exist` | `psql -U postgres -c "CREATE DATABASE kanban;"` |
| `401 Unauthorized` | Войдите заново — JWT мог истечь |
| `503 Google sign-in is not configured` | Добавить `GOOGLE_CLIENT_ID` в `.env` |
| `503 Stripe is not configured` | Добавить Stripe-переменные в `backend2/.env` и перезапустить бэкенд |
| `503` на checkout при запущенном бэкенде | На `:8000` могут висеть старые `uvicorn`-процессы — запустите бэкенд на `:8001` и укажите `VITE_API_BASE_URL=http://127.0.0.1:8001` |
| `Missing required parameter: client_id` (Google) | Настроить `VITE_GOOGLE_CLIENT_ID` на фронтенде и перезапустить dev-сервер |
| Пустой список пользователей | Запустите `scripts/seed_users.py` |
| Cloudflare **521** на slava.vevi.monster | Запустите `deploy/bootstrap_nginx.sh` на дроплете |
