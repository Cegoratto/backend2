"""Создать 10 тестовых пользователей с разными ролями."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.models.user import User

TEST_PASSWORD = "password123"

TEST_USERS = [
    ("Алексей", "alexey@example.com", "Frontend Developer"),
    ("Мария", "maria@example.com", "Backend Developer"),
    ("Иван", "ivan@example.com", "Fullstack Developer"),
    ("Ольга", "olga@example.com", "Mobile Developer"),
    ("Дмитрий", "dmitry@example.com", "QA Engineer"),
    ("Елена", "elena@example.com", "DevOps Engineer"),
    ("Анна", "anna@example.com", "UI/UX Designer"),
    ("Сергей", "sergey@example.com", "Product Manager"),
    ("Наталья", "natalia@example.com", "Team Lead"),
    ("Павел", "pavel@example.com", "Project Manager"),
]


async def seed_users() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        created = 0
        skipped = 0

        for name, email, team_role in TEST_USERS:
            existing = await session.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            session.add(
                User(
                    email=email,
                    password_hash=hash_password(TEST_PASSWORD),
                    name=name,
                    team_role=team_role,
                )
            )
            created += 1

        await session.commit()

    print(f"Done: created {created}, skipped {skipped} (already exist)")
    print(f"Password for all test users: {TEST_PASSWORD}")
    print()
    print("Users:")
    for name, email, team_role in TEST_USERS:
        print(f"  {name:10} {email:25} {team_role}")


if __name__ == "__main__":
    asyncio.run(seed_users())
