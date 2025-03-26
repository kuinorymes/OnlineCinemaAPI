import asyncio
from celery import shared_task
from sqlalchemy import select
from database.models.users import (
    TokenBaseModel,
    PasswordResetTokenModel,
    ActivationTokenModel,
)
from datetime import datetime

from database.session_postgresql import postgres_async_session


async def delete_expired_tokens(token_model: TokenBaseModel, type_of_token: str):
    async with postgres_async_session() as db:
        expired_tokens_stmt = select(token_model).where(
            token_model.expires_at < datetime.now()
        )
        expired_tokens_result = await db.execute(expired_tokens_stmt)
        expired_tokens = expired_tokens_result.scalars().all()

        if expired_tokens:
            for token in expired_tokens:
                await db.delete(token)
            await db.commit()
            print(f"Deleted {len(expired_tokens)} expired  {type_of_token} tokens.")
            return len(expired_tokens)
        print(f"No expired {type_of_token} tokens found")
        return 0


async def run_tasks():
    task1 = asyncio.create_task(delete_expired_tokens(PasswordResetTokenModel, "password reset"))
    task2 = asyncio.create_task(delete_expired_tokens(ActivationTokenModel, "activation"))
    # await asyncio.gather(
    #     delete_expired_tokens(PasswordResetTokenModel, "password reset"),
    #     delete_expired_tokens(ActivationTokenModel, "activation"),
    #     return_exceptions=True
    #)
    await task1
    await task2


@shared_task
def delete_expired_tokens_wrapper():
    asyncio.run(run_tasks())
