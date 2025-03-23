from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload
from starlette import status
from typing import Annotated, cast
from datetime import datetime, timezone, timedelta

from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from config import BaseAppSettings
from exceptions.security import BaseSecurityError
from schemas.users import (
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema,
    UserActivation,
    UserResendActivationEmail,
    UserLoginRequestSchema,
    UserLoginResponseSchema,
    RefreshTokenRequestSchema,
    RefreshTokenResponseSchema,
    ChangePasswordRequestSchema,
    ResetPasswordRequestSchema,
    ResetPasswordCompleteRequestSchema,
    ResetPasswordResponseSchema,
)
from notifications.tasks import (
    send_register_activate_email,
    send_reset_password_email,
)
from database.models.users import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    RefreshTokenModel,
    PasswordResetTokenModel,
)
from database.session_sqlite import get_sqlite_db
from security.interfaces import JWTAuthManagerInterface
from security.password import hash_password

from config.dependencies import (
    get_settings,
    get_jwt_auth_manager,
)

router = APIRouter()

DB = Annotated[AsyncSession, Depends(get_sqlite_db)]


@router.post(
    "/registration/",
    response_model=UserRegistrationResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def register(
        data: UserRegistrationRequestSchema,
        background_tasks: BackgroundTasks,
        settings: Annotated[BaseAppSettings, Depends(get_settings)],
        db: DB,
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
            email=cast(str, data.email),
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
    "/registration/{activation_token}/",
    status_code=status.HTTP_200_OK
)
async def activate_user(
        activation_token: str,
        db: DB,
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
    "/registration/resend-email/",
    status_code=status.HTTP_200_OK,
)
async def resend_activation_email(
        data: UserResendActivationEmail,
        background_tasks: BackgroundTasks,
        settings: Annotated[BaseAppSettings, Depends(get_settings)],
        db: DB,
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


@router.post(
    "/login/",
    status_code=status.HTTP_200_OK,
    response_model=UserLoginResponseSchema,
)
async def login(
        data: UserLoginRequestSchema,
        db: DB,
        settings: Annotated[BaseAppSettings, Depends(get_settings)],
        jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
):
    user_stmt = select(UserModel).where(UserModel.email == data.email)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user or not user.verify_password(data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not activated."
        )

    token = jwt_manager.create_refresh_token({"user_id": user.id})
    try:
        refresh_token = RefreshTokenModel.create(
            user_id=user.id,
            days_valid=settings.LOGIN_DAYS_VALID,
            token=token,
        )
        db.add(refresh_token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login."
        )

    access_token = jwt_manager.create_access_token({"user_id": user.id})
    return UserLoginResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token.token,
    )


oauth_scheme = OAuth2PasswordBearer(tokenUrl="/users/login/")


async def get_current_user(
        db: DB,
        token: Annotated[str, Depends(oauth_scheme)],
        jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
):
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token."
        )
    user_stmt = select(UserModel).where(UserModel.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    return user


@router.post(
    "/logout/",
    status_code=status.HTTP_200_OK,
)
async def logout(
        user: Annotated[UserModel, Depends(get_current_user)],
        db: DB,
):
    stmt = delete(RefreshTokenModel).where(RefreshTokenModel.user_id == user.id)
    await db.execute(stmt)
    await db.commit()
    return {
        "message": "You have been successfully logged out."
    }


@router.post(
    "/refresh/",
    response_model=RefreshTokenResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def refresh_access_token(
        token_data: RefreshTokenRequestSchema,
        db: DB,
        jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
):
    try:
        payload = jwt_manager.decode_refresh_token(token_data.refresh_token)
        user_id = payload.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    token_stmt = select(RefreshTokenModel).where(RefreshTokenModel.token == token_data.refresh_token)
    token_result = await db.execute(token_stmt)
    token = token_result.scalar_one_or_none()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    user_stmt = select(UserModel).where(UserModel.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    access_token = jwt_manager.create_access_token({"user_id": user.id})

    return RefreshTokenResponseSchema(
        access_token=access_token
    )


@router.post("/change-password/")
async def change_password(
        user: Annotated[UserModel, Depends(get_current_user)],
        data: ChangePasswordRequestSchema,
        db: DB,
):
    if not user.verify_password(data.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    if data.old_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your new password should be different from the old one."
        )

    user.hashed_password = hash_password(data.new_password)

    await db.commit()
    return {
        "message": "Your password has been changed!"
    }


@router.post(
    "/reset-password/",
    status_code=status.HTTP_200_OK,
)
async def reset_password(
        data: ResetPasswordRequestSchema,
        db: DB,
        background_tasks: BackgroundTasks,
        settings: Annotated[BaseAppSettings, Depends(get_settings)],
):
    user_stmt = select(UserModel).where(UserModel.email == data.email)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user or not user.is_active:
        return {
            "message": "If you're registered you will receive an email."
        }

    reset_token = PasswordResetTokenModel(
        user_id=cast(int, user.id)
    )

    db.add(reset_token)
    await db.commit()

    reset_link = f"{settings.BASE_URL}/users/reset-password/{reset_token.token}/"

    background_tasks.add_task(
        send_reset_password_email,
        user.email,
        reset_link,
    )
    return {
        "message": "If you're registered you will receive an email."
    }


@router.get("/reset-password/{token}")
async def reset_password_check_token(
        token: str,
        db: DB,
):
    token_stmt = select(PasswordResetTokenModel).options(
        joinedload(PasswordResetTokenModel.user)
    ).where(PasswordResetTokenModel.token == token)

    token_result = await db.execute(token_stmt)
    reset_token = token_result.scalar_one_or_none()

    if not reset_token or reset_token.expires_at < datetime.now(timezone.utc) or not reset_token.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired token."
        )
    return ResetPasswordResponseSchema(
        valid=True
    )


@router.post(
    "/reset-password/{token}/",
    status_code=status.HTTP_200_OK,
)
async def reset_password_complete(
        token: str,
        data: ResetPasswordCompleteRequestSchema,
        db: DB,
):
    token_stmt = select(PasswordResetTokenModel).options(
        joinedload(PasswordResetTokenModel.user)
    ).where(PasswordResetTokenModel.token == token)

    token_result = await db.execute(token_stmt)
    reset_token = token_result.scalar_one_or_none()

    if not reset_token or reset_token.expires_at < datetime.now(timezone.utc) or not reset_token.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired token."
        )
    reset_token.user.hashed_password = hash_password(data.new_password)

    await db.delete(reset_token)
    await db.commit()

    return {
        "message": "Your password has been successfully changed."
    }
