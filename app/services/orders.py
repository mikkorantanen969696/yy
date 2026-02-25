"""
Order service layer.

All business logic should end up here, not inside handlers.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_photo import OrderPhoto
from app.models.response import Response
from app.utils.constants import ORDER_STATUSES


async def create_order(session: AsyncSession, data: dict) -> Order:
    """Create and persist a new order."""
    order = Order(**data)
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    """Fetch order by id."""
    result = await session.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def list_all_orders(session: AsyncSession) -> list[Order]:
    """List all orders (admin)."""
    result = await session.execute(select(Order))
    return list(result.scalars().all())


async def list_orders_by_manager(session: AsyncSession, manager_id: int) -> list[Order]:
    """List orders created by manager."""
    result = await session.execute(select(Order).where(Order.manager_id == manager_id))
    return list(result.scalars().all())


async def list_orders_by_master(session: AsyncSession, master_id: int) -> list[Order]:
    """List orders assigned to master."""
    result = await session.execute(select(Order).where(Order.master_id == master_id))
    return list(result.scalars().all())


async def assign_master(session: AsyncSession, order: Order, master_id: int) -> Order:
    """Assign master to order if available."""
    order.master_id = master_id
    order.status = ORDER_STATUSES["assigned"]
    await session.commit()
    await session.refresh(order)
    return order


async def unassign_master(session: AsyncSession, order: Order) -> Order:
    """Remove master assignment and revert to published."""
    order.master_id = None
    order.status = ORDER_STATUSES["published"]
    await session.commit()
    await session.refresh(order)
    return order


async def set_status(session: AsyncSession, order: Order, status: str) -> Order:
    """Update order status."""
    order.status = status
    await session.commit()
    await session.refresh(order)
    return order


async def register_response(session: AsyncSession, order_id: int, master_id: int) -> Response:
    """Record master response to an order."""
    resp = Response(order_id=order_id, master_id=master_id)
    session.add(resp)
    await session.commit()
    await session.refresh(resp)
    return resp


async def add_photo(session: AsyncSession, order_id: int, file_id: str, photo_type: str) -> OrderPhoto:
    """Store photo metadata for order."""
    photo = OrderPhoto(order_id=order_id, file_id=file_id, type=photo_type)
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo
