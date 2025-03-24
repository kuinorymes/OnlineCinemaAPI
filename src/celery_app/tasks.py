import asyncio
from celery import shared_task
from sqlalchemy import select
from database.models.users import PasswordResetTokenModel
from datetime import datetime

from database.session_sqlite import AsyncSQLiteSessionLocal


@shared_task
async def delete_expired_tokens():
    async with AsyncSQLiteSessionLocal() as db:
        expired_tokens_stmt = select(PasswordResetTokenModel).where(
            PasswordResetTokenModel.expires_at < datetime.now()
        )
        expired_tokens_result = await db.execute(expired_tokens_stmt)
        expired_tokens = expired_tokens_result.scalars().all()

        if expired_tokens:
            for token in expired_tokens:
                await db.delete(token)

            await db.commit()
            print(f"Deleted {len(expired_tokens)} expired tokens.")
            return len(expired_tokens)
        print("No expired tokens found")
        return 0


@shared_task
def delete_expired_tokens_wrapper():
    return asyncio.run(delete_expired_tokens())
