from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from starlette import status
from typing import Annotated
from datetime import datetime, timezone

from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from schemas.users import (
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema,
    UserActivation,
    UserResendActivationEmail,
)
from notifications.tasks import send_register_activate_email
from database.models.users import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel
)
from database.session_sqlite import get_sqlite_db
from security.password import hash_password

from config.dependencies import get_settings


settings = get_settings()


router = APIRouter()


@router.post(
    "/users/registration/",
    response_model=UserRegistrationResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def register(
        data: UserRegistrationRequestSchema,
        background_tasks: BackgroundTasks,
        db: Annotated[AsyncSession, Depends(get_sqlite_db)]
):
    user_stmt = select(UserModel).where(UserModel.email == data.email)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email {user.email} already exists."
        )

    group_stmt = select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
    group_result = await db.execute(group_stmt)
    group = group_result.scalar_one_or_none()

    if not group:
        group = UserGroupModel(name=UserGroupEnum.USER)
        db.add(group)
        await db.flush()
    try:
        user = UserModel(
            email=data.email,
            hashed_password=hash_password(data.password),
            group_id=group.id,
        )

        db.add(user)
        await db.flush()

        activation_token = ActivationTokenModel(
            user_id=user.id
        )
        db.add(activation_token)
        await db.commit()

        activation_link = f"{settings.BASE_URL}/users/registration/{activation_token.token}/"

        background_tasks.add_task(
            send_register_activate_email,
            user.email,
            activation_link,
        )
        return user
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during registration: {e}"
        )




@router.get(
    "/users/registration/{activation_token}/",
    status_code=status.HTTP_200_OK
)
async def activate_user(
        activation_token: str,
        db: Annotated[AsyncSession, Depends(get_sqlite_db)],
):
    token_stmt = select(ActivationTokenModel).options(
        joinedload(ActivationTokenModel.user)
    ).where(
        ActivationTokenModel.token == activation_token
    )
    token_result = await db.execute(token_stmt)
    token = token_result.scalar_one_or_none()

    if not token or token.expires_at < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired token.",
        )

    if token.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is already activated."
        )

    token.user.is_active = True
    await db.delete(token)
    await db.commit()
    return UserActivation(
        message="Your account has been successfully activated."
    )


@router.post(
    "/users/registration/resend-email/",
    status_code=status.HTTP_200_OK,
)
async def resend_activation_email(
        data: UserResendActivationEmail,
        background_tasks: BackgroundTasks,
        db: Annotated[AsyncSession, Depends(get_sqlite_db)]
):
    user_stmt = select(UserModel).options(
        joinedload(UserModel.activation_token)
    ).where(UserModel.email == data.email)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        return UserActivation(
            message="If you're registered, you will receive an email with the activation link."
        )
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is already activated."
        )

    if user.activation_token is not None:
        await db.delete(user.activation_token)
        await db.flush()

    new_token = ActivationTokenModel(user_id=user.id)
    db.add(new_token)
    await db.commit()

    activation_link = f"{settings.BASE_URL}/users/registration/{new_token.token}/"

    background_tasks.add_task(
        send_register_activate_email,
        user.email,
        activation_link,
    )

    return UserActivation(
        message="The email with the activation link has been sent to your email."
    )
