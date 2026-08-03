-- Создание базы данных для backend2 (выполнить один раз)
-- psql -U postgres -f scripts/create_database.sql

SELECT 'CREATE DATABASE kanban'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'kanban')\gexec
