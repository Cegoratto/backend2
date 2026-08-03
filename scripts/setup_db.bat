@echo off
REM Создание БД kanban для локального PostgreSQL (без Docker)
REM Требуется: PostgreSQL установлен и psql в PATH

psql -U postgres -c "SELECT 1 FROM pg_database WHERE datname = 'kanban'" | findstr /C:"1" >nul
if %ERRORLEVEL% EQU 0 (
    echo Database kanban already exists.
) else (
    psql -U postgres -c "CREATE DATABASE kanban;"
    echo Database kanban created.
)

echo.
echo Next steps:
echo   .\.venv\Scripts\activate
echo   alembic upgrade head
echo   uvicorn app.main:app --reload --port 8000
