# Kanban Backend (FastAPI)

Python-бэкенд для Kanban-приложения. Заменяет Supabase (auth + CRUD) и Cloudflare Worker (AI).

Подробная документация миграции: [`second_project/docs/REST_MIGRATION.md`](../second_project/docs/REST_MIGRATION.md)

## Стек

- FastAPI
- SQLAlchemy 2.x (async)
- JWT auth (email/password)
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
```

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
| POST | `/api/auth/login` | Вход |
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

Все защищённые эндпоинты требуют `Authorization: Bearer <token>`.

## Подключение фронтенда

Фронтенд (`second_project`) уже мигрирован на REST API.

```powershell
# Терминал 1
cd backend2 && uvicorn app.main:app --reload --port 8000

# Терминал 2
cd second_project && npm run dev
```

Vite proxy: `/api` → `http://localhost:8000`

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

## Устранение проблем

| Ошибка | Решение |
|--------|---------|
| `connection refused` :5432 | Используйте SQLite или запустите PostgreSQL |
| `database "kanban" does not exist` | `psql -U postgres -c "CREATE DATABASE kanban;"` |
| `401 Unauthorized` | Войдите заново — JWT мог истечь |
| Пустой список пользователей | Запустите `scripts/seed_users.py` |
