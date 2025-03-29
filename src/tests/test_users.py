import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient

from database.models.users import UserModel, UserGroupModel, UserGroupEnum, ActivationTokenModel
from schemas.users import UserRegistrationRequestSchema, UserRegistrationResponseSchema
from config.settings import BaseAppSettings


@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=BaseAppSettings)
    settings.BASE_URL = "http://testserver"
    settings.API_VERSION = "/api/v1"
    return settings


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_background_tasks():
    return MagicMock(spec=BackgroundTasks)


@pytest.fixture
def valid_registration_data():
    return UserRegistrationRequestSchema(
        email="test@example.com",
        password="StrongPa$$w0rd",
        confirm_password="StrongPa$$w0rd",
    )


@pytest.mark.asyncio
@patch("routes.users.send_register_activate_email")
@patch("security.password.hash_password")
async def test_register_successful(
        mock_hash_password,
        mock_send_email,
        mock_db,
        mock_settings,
        mock_background_tasks,
        valid_registration_data,
):
    mock_hash_password.return_value = "hashedpassword123"

    user_result_mock = MagicMock()
    user_result_mock.scalar_one_or_none.return_value = None

    group_result_mock = MagicMock()
    group_mock = MagicMock(spec=UserGroupModel)
    group_mock.id = 1
    group_result_mock.scalar_one_or_none.return_value = group_mock

    mock_db.execute.side_effect = [user_result_mock, group_result_mock]

    def side_effect_add(obj):
        if isinstance(obj, UserModel):
            obj.id = 1

    mock_db.add.side_effect = side_effect_add

    from routes.users import register
    result = await register(
        valid_registration_data,
        mock_background_tasks,
        mock_settings,
        mock_db,
    )

    mock_db.execute.assert_called()
    assert mock_db.execute.call_count == 2
    mock_db.add.assert_called()
    assert mock_db.add.call_count == 2
    mock_db.flush.assert_called()
    mock_db.commit.assert_called_once()

    mock_background_tasks.add_task.assert_called_once()
    call_args = mock_background_tasks.add_task.call_args[0]
    assert call_args[0] == mock_send_email
    assert call_args[1] == valid_registration_data.email
    assert "http://testserver/api/v1/users/registration/" in call_args[2]

    assert isinstance(result, UserModel)
    assert result.email == valid_registration_data.email
    assert result.hashed_password == "hashedpassword123"


@pytest.mark.asyncio
async def test_register_user_already_exists(
        mock_db,
        mock_settings,
        mock_background_tasks,
        valid_registration_data,
):
    existing_user = MagicMock(spec=UserModel)
    existing_user.email = valid_registration_data.email

    user_result_mock = MagicMock()
    user_result_mock.scalar_one_or_none.return_value = existing_user

    mock_db.execute.return_value = user_result_mock

    from routes.users import register
    with pytest.raises(HTTPException) as exc_info:
        await register(
            valid_registration_data,
            mock_background_tasks,
            mock_settings,
            mock_db,
        )

    assert exc_info.value.status_code == 400
    assert f"User with email {existing_user.email} already exists" in str(exc_info.value.detail)


@pytest.mark.asyncio
@patch("security.password.hash_password")
async def test_register_create_group_if_not_exists(
        mock_hash_password,
        mock_db,
        mock_settings,
        mock_background_tasks,
        valid_registration_data,
):
    mock_hash_password.return_value = "hashedpassword123"

    user_result_mock = MagicMock()
    user_result_mock.scalar_one_or_none.return_value = None

    group_result_mock = MagicMock()
    group_result_mock.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [user_result_mock, group_result_mock]

    def side_effect_add(obj):
        if isinstance(obj, UserGroupModel):
            obj.id = 1
        elif isinstance(obj, UserModel):
            obj.id = 1

    mock_db.add.side_effect = side_effect_add

    from routes.users import register
    result = await register(
        valid_registration_data,
        mock_background_tasks,
        mock_settings,
        mock_db,
    )

    assert mock_db.add.call_count == 3
    assert mock_db.flush.call_count == 2

    group_add_call = [call for call in mock_db.add.call_args_list if isinstance(call[0][0], UserGroupModel)]
    assert len(group_add_call) == 1


@pytest.mark.asyncio
@patch("security.password.hash_password")
async def test_register_database_error(
        mock_hash_password,
        mock_db,
        mock_settings,
        mock_background_tasks,
        valid_registration_data,
):
    mock_hash_password.return_value = "hashedpassword123"

    user_result_mock = MagicMock()
    user_result_mock.scalar_one_or_none.return_value = None

    group_result_mock = MagicMock()
    group_mock = MagicMock(spec=UserGroupModel)
    group_mock.id = 1
    group_result_mock.scalar_one_or_none.return_value = group_mock

    mock_db.execute.side_effect = [user_result_mock, group_result_mock]

    mock_db.flush.side_effect = SQLAlchemyError("Database error")

    from routes.users import register
    with pytest.raises(HTTPException) as exc_info:
        await register(
            valid_registration_data,
            mock_background_tasks,
            mock_settings,
            mock_db,
        )

    assert exc_info.value.status_code == 500
    assert "An error occurred during registration" in str(exc_info.value.detail)
