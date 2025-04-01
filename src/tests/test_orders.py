
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from decimal import Decimal
from datetime import datetime

from database.models.shopping_cart import CartModel
from database.models.payments import PaymentModel
from routes.orders import (
    create_order,
    get_user_orders,
    get_order_by_id,
    cancel_order,
)
from schemas.orders import OrderCreateSchema
from database.models.orders import OrderStatusEnum

def fake_execute_result(fetchall_return=None, scalars_all_return=None, scalar_one_or_none_return=None):
    fake_result = MagicMock()
    fake_result.fetchall = MagicMock(return_value=fetchall_return)
    fake_scalars = MagicMock()
    fake_scalars.all = MagicMock(return_value=scalars_all_return)
    fake_result.scalars.return_value = fake_scalars
    fake_result.scalar_one_or_none = MagicMock(return_value=scalar_one_or_none_return)
    return fake_result


class DummyOrderItem:
    def __init__(self, id, price_at_order):
        self.id = id
        self.price_at_order = price_at_order


class DummyOrder:
    def __init__(self, id, user_id, total_amount, status, order_items, created_at=None):
        self.id = id
        self.user_id = user_id
        self.total_amount = total_amount
        self.status = status
        self.order_items = order_items
        self.created_at = created_at or datetime.utcnow()


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    return user


@pytest.fixture
def valid_order_data():
    return OrderCreateSchema(items=[{"movie_id": 1}, {"movie_id": 2}])



@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_create_order_success(mock_get_current_user, mock_db, valid_order_data, mock_user):
    mock_get_current_user.return_value = mock_user

    fake_result_1 = fake_execute_result(fetchall_return=[])
    fake_result_2 = fake_execute_result(scalars_all_return=[])

    movie1 = MagicMock()
    movie1.id = 1
    movie1.price = Decimal("10.00")
    movie2 = MagicMock()
    movie2.id = 2
    movie2.price = Decimal("15.00")
    fake_result_3 = fake_execute_result(scalars_all_return=[movie1, movie2])

    mock_db.execute.side_effect = [fake_result_1, fake_result_2, fake_result_3]

    result = await create_order(valid_order_data, mock_db, mock_user)
    assert result.total_amount == Decimal("25.00")
    assert len(result.order_items) == 2
    assert result.status == OrderStatusEnum.PENDING


@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_create_order_already_purchased(mock_get_current_user, mock_db, valid_order_data, mock_user):
    mock_get_current_user.return_value = mock_user

    fake_result = fake_execute_result(fetchall_return=[(1,), (2,)])
    mock_db.execute.return_value = fake_result

    with pytest.raises(HTTPException) as exc_info:
        await create_order(valid_order_data, mock_db, mock_user)
    assert exc_info.value.status_code == 400
    assert "Movies with id: [1, 2] already purchased." in str(exc_info.value.detail)


@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_create_order_with_pending_order(mock_get_current_user, mock_db, valid_order_data, mock_user):
    mock_get_current_user.return_value = mock_user

    fake_result_1 = fake_execute_result(fetchall_return=[])
    fake_result_2 = fake_execute_result(scalars_all_return=[1])

    mock_db.execute.side_effect = [fake_result_1, fake_result_2]

    with pytest.raises(HTTPException) as exc_info:
        await create_order(valid_order_data, mock_db, mock_user)
    assert exc_info.value.status_code == 400
    assert "You already have pending orders with these movies" in str(exc_info.value.detail)


@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_create_order_movie_not_found(mock_get_current_user, mock_db, valid_order_data, mock_user):
    mock_get_current_user.return_value = mock_user

    fake_result_1 = fake_execute_result(fetchall_return=[])
    fake_result_2 = fake_execute_result(scalars_all_return=[])
    movie1 = MagicMock()
    movie1.id = 1
    movie1.price = Decimal("10.00")
    fake_result_3 = fake_execute_result(scalars_all_return=[movie1])

    mock_db.execute.side_effect = [fake_result_1, fake_result_2, fake_result_3]

    with pytest.raises(HTTPException) as exc_info:
        await create_order(valid_order_data, mock_db, mock_user)
    assert exc_info.value.status_code == 404
    assert "2" in str(exc_info.value.detail)



@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_get_user_orders(mock_get_current_user, mock_db, mock_user):
    mock_get_current_user.return_value = mock_user
    dummy_order_item = DummyOrderItem(id=1, price_at_order=Decimal("19.99"))
    order = DummyOrder(
        id=1,
        user_id=1,
        total_amount=Decimal("19.99"),
        status=OrderStatusEnum.PENDING,
        order_items=[dummy_order_item],
        created_at=datetime.utcnow()
    )
    fake_result = fake_execute_result(scalars_all_return=[order])
    mock_db.execute.return_value = fake_result

    result = await get_user_orders(mock_db, mock_user)
    assert len(result.orders) == 1
    assert result.orders[0].id == 1



@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_get_order_by_id(mock_get_current_user, mock_db, mock_user):
    mock_get_current_user.return_value = mock_user
    dummy_order_item = DummyOrderItem(id=1, price_at_order=Decimal("19.99"))
    order = DummyOrder(
        id=1,
        user_id=1,
        total_amount=Decimal("19.99"),
        status=OrderStatusEnum.PENDING,
        order_items=[dummy_order_item],
        created_at=datetime.utcnow()
    )
    fake_result = fake_execute_result(scalar_one_or_none_return=order)
    mock_db.execute.return_value = fake_result

    result = await get_order_by_id(1, mock_db, mock_user)
    assert result.id == 1


@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_get_order_by_id_not_found(mock_get_current_user, mock_db, mock_user):
    mock_get_current_user.return_value = mock_user
    fake_result = fake_execute_result(scalar_one_or_none_return=None)
    mock_db.execute.return_value = fake_result

    with pytest.raises(HTTPException) as exc_info:
        await get_order_by_id(1, mock_db, mock_user)
    assert exc_info.value.status_code == 404
    assert "Order with id: 1 was not found" in str(exc_info.value.detail)


# --- Тести для cancel_order ---

@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_cancel_order_success(mock_get_current_user, mock_db, mock_user):
    mock_get_current_user.return_value = mock_user
    dummy_order_item = DummyOrderItem(id=1, price_at_order=Decimal("19.99"))
    order = DummyOrder(
        id=1,
        user_id=1,
        total_amount=Decimal("19.99"),
        status=OrderStatusEnum.PENDING,
        order_items=[dummy_order_item],
        created_at=datetime.utcnow()
    )
    fake_result = fake_execute_result(scalar_one_or_none_return=order)
    mock_db.execute.return_value = fake_result

    result = await cancel_order(1, mock_db, mock_user)
    assert result["detail"] == "Order canceled successfully"


@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_cancel_order_not_pending(mock_get_current_user, mock_db, mock_user):
    mock_get_current_user.return_value = mock_user
    dummy_order_item = DummyOrderItem(id=1, price_at_order=Decimal("19.99"))
    order = DummyOrder(
        id=1,
        user_id=1,
        total_amount=Decimal("19.99"),
        status=OrderStatusEnum.PAID,
        order_items=[dummy_order_item],
        created_at=datetime.utcnow()
    )
    fake_result = fake_execute_result(scalar_one_or_none_return=order)
    mock_db.execute.return_value = fake_result

    with pytest.raises(HTTPException) as exc_info:
        await cancel_order(1, mock_db, mock_user)
    assert exc_info.value.status_code == 400
    assert "Only pending orders can be cancelled" in str(exc_info.value.detail)


@pytest.mark.asyncio
@patch("routes.orders.get_current_user")
async def test_cancel_order_not_found(mock_get_current_user, mock_db, mock_user):
    mock_get_current_user.return_value = mock_user
    fake_result = fake_execute_result(scalar_one_or_none_return=None)
    mock_db.execute.return_value = fake_result

    with pytest.raises(HTTPException) as exc_info:
        await cancel_order(1, mock_db, mock_user)
    assert exc_info.value.status_code == 404
    assert "Order with id: 1 was not found" in str(exc_info.value.detail)
