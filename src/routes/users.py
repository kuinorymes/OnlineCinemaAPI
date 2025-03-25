from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload
from starlette import status
from typing import Annotated, cast
from pydantic import HttpUrl
from datetime import datetime, timezone, timedelta

from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from config import BaseAppSettings
from exceptions.security import BaseSecurityError
from exceptions.storage import S3FileUploadError
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
from schemas.profiles import (
    UserProfileResponseSchema,
    ProfileCreateRequestSchema,
    ProfileCreateResponseSchema,
)
from notifications.tasks import (
    send_register_activate_email,
    send_reset_password_email,
    send_reset_password_email_complete,
)
from database.models.users import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    RefreshTokenModel,
    PasswordResetTokenModel,
    UserProfileModel,
)
from database.session_sqlite import get_sqlite_db
from security.interfaces import JWTAuthManagerInterface
from security.password import hash_password

from config.dependencies import (
    get_settings,
    get_jwt_auth_manager,
    get_s3_storage_client,
)
from storages.interfaces import S3StorageInterface

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
            detail=f"User with email {user.email} already exists.",
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

        activation_token = ActivationTokenModel(user_id=user.id)
        db.add(activation_token)
        await db.commit()

        activation_link = f"{settings.BASE_URL}{settings.API_VERSION}/users/registration/{activation_token.token}/"

        background_tasks.add_task(
            send_register_activate_email,
            user.email,
            activation_link,
        )
        return user
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during registration: {e}",
        )


@router.get("/registration/{activation_token}/", status_code=status.HTTP_200_OK)
async def activate_user(
        activation_token: str,
        db: DB,
):
    token_stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .where(ActivationTokenModel.token == activation_token)
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
            detail="This account is already activated.",
        )

    token.user.is_active = True
    await db.delete(token)
    await db.commit()
    return UserActivation(message="Your account has been successfully activated.")


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
    user_stmt = (
        select(UserModel)
        .options(joinedload(UserModel.activation_token))
        .where(UserModel.email == data.email)
    )
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        return UserActivation(
            message="If you're registered, you will receive an email with the activation link."
        )
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is already activated.",
        )

    if user.activation_token is not None:
        await db.delete(user.activation_token)
        await db.flush()

    new_token = ActivationTokenModel(user_id=user.id)
    db.add(new_token)
    await db.commit()

    activation_link = f"{settings.BASE_URL}{settings.API_VERSION}/users/registration/{new_token.token}/"

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
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is not activated."
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
            detail="An error occurred during login.",
        )

    access_token = jwt_manager.create_access_token({"user_id": user.id})
    return UserLoginResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token.token,
    )


oauth_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login/")


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
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token."
        )
    user_stmt = select(UserModel).where(UserModel.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
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
    return {"message": "You have been successfully logged out."}


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

    token_stmt = select(RefreshTokenModel).where(
        RefreshTokenModel.token == token_data.refresh_token
    )
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

    return RefreshTokenResponseSchema(access_token=access_token)


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
            detail="Your new password should be different from the old one.",
        )

    user.hashed_password = hash_password(data.new_password)

    await db.commit()
    return {"message": "Your password has been changed!"}


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
        return {"message": "If you're registered you will receive an email."}

    existing_token_stmt = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id
    )
    existing_token_result = await db.execute(existing_token_stmt)
    existing_token = existing_token_result.scalar_one_or_none()
    if existing_token:
        await db.delete(existing_token)
        await db.flush()

    reset_token = PasswordResetTokenModel(user_id=cast(int, user.id))

    db.add(reset_token)
    await db.commit()

    reset_link = f"{settings.BASE_URL}{settings.API_VERSION}/users/reset-password/{reset_token.token}/"

    background_tasks.add_task(
        send_reset_password_email,
        user.email,
        reset_link,
    )
    return {"message": "If you're registered you will receive an email."}


@router.get("/reset-password/{token}/")
async def reset_password_check_token(
        token: str,
        db: DB,
):
    token_stmt = (
        select(PasswordResetTokenModel)
        .options(joinedload(PasswordResetTokenModel.user))
        .where(PasswordResetTokenModel.token == token)
    )

    token_result = await db.execute(token_stmt)
    reset_token = token_result.scalar_one_or_none()

    if (
            not reset_token
            or reset_token.expires_at < datetime.now()
            or not reset_token.user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired token."
        )
    return ResetPasswordResponseSchema(valid=True)


@router.post(
    "/reset-password/{token}/",
    status_code=status.HTTP_200_OK,
)
async def reset_password_complete(
        token: str,
        data: ResetPasswordCompleteRequestSchema,
        db: DB,
        background_tasks: BackgroundTasks,
        settings: Annotated[BaseAppSettings, Depends(get_settings)],
):
    token_stmt = (
        select(PasswordResetTokenModel)
        .options(joinedload(PasswordResetTokenModel.user))
        .where(PasswordResetTokenModel.token == token)
    )

    token_result = await db.execute(token_stmt)
    reset_token = token_result.scalar_one_or_none()

    if (
            not reset_token
            or reset_token.expires_at < datetime.now()
            or not reset_token.user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired token."
        )
    reset_token.user.hashed_password = hash_password(data.new_password)

    await db.delete(reset_token)
    await db.commit()

    login_link = f"{settings.BASE_URL}{settings.API_VERSION}/users/login/"

    background_tasks.add_task(
        send_reset_password_email_complete,
        reset_token.user.email,
        login_link,
    )

    return {"message": "Your password has been successfully changed."}


@router.get(
    "/my-profile/",
    status_code=status.HTTP_200_OK,
    response_model=UserProfileResponseSchema
)
async def get_user_profile(
        db: DB,
        user: Annotated[UserModel, Depends(get_current_user)],
        s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
):
    profile_stmt = select(UserProfileModel).where(UserProfileModel.user_id == user.id)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You don't have a profile yet."
        )

    avatar_url = await s3_client.get_file_url(profile.avatar)

    return UserProfileResponseSchema(
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar=cast(HttpUrl, avatar_url)
    )


@router.post(
    "/create-profile/",
    status_code=status.HTTP_201_CREATED,
    response_model=ProfileCreateResponseSchema,
)
async def create_profile(
        data: Annotated[ProfileCreateRequestSchema, Depends(ProfileCreateRequestSchema.from_form)],
        user: Annotated[UserModel, Depends(get_current_user)],
        db: DB,
        s3_client: Annotated[S3StorageInterface, Depends(get_s3_storage_client)],
):
    profile_stmt = select(UserProfileModel).where(UserProfileModel.user_id == user.id)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    if profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a profile."
        )

    avatar_bytes = await data.avatar.read()
    avatar_key = f"avatars/{user.id}_{data.avatar.filename}"

    try:
        await s3_client.upload_file(
            file_name=avatar_key,
            file_data=avatar_bytes,
        )
    except S3FileUploadError as e:
        print(f"Error uploading avatar to S3: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar. Please try again later."
        )

    new_profile = UserProfileModel(
        user_id=user.id,
        first_name=data.first_name,
        last_name=data.last_name,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        info=data.info,
        avatar=avatar_key
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    avatar_url = await s3_client.get_file_url(new_profile.avatar)

    return ProfileCreateResponseSchema(
        id=new_profile.id,
        user_id=new_profile.user_id,
        first_name=new_profile.first_name,
        last_name=new_profile.last_name,
        gender=new_profile.gender,
        date_of_birth=new_profile.date_of_birth,
        info=new_profile.info,
        avatar=cast(HttpUrl, avatar_url)
    )
