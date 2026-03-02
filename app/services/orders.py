"""
Order service layer.

All business logic should end up here, not inside handlers.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_photo import OrderPhoto
from app.models.order_visibility import OrderVisibility
from app.models.response import Response
from app.utils.constants import ORDER_STATUSES

DEFAULT_MASTER_VISIBLE_FIELDS = {
    "date",
    "time",
    "address",
    "type",
    "equipment",
    "conditions",
    "comment",
}


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


async def list_recent_orders(
    session: AsyncSession,
    status: str | None = None,
    city: str | None = None,
    limit: int = 20,
) -> list[Order]:
    """List latest orders with optional filters."""
    stmt = select(Order)
    if status:
        stmt = stmt.where(Order.status == status)
    if city:
        stmt = stmt.where(Order.city == city)

    stmt = stmt.order_by(Order.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
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


def _normalize_visible_fields(fields: set[str]) -> str:
    """Serialize selected fields as a stable comma-separated list."""
    clean = {f.strip() for f in fields if f and f.strip()}
    return ",".join(sorted(clean))


def _parse_visible_fields(value: str | None) -> set[str]:
    """Deserialize comma-separated fields from DB."""
    if not value:
        return set(DEFAULT_MASTER_VISIBLE_FIELDS)
    return {part.strip() for part in value.split(",") if part.strip()}


async def set_master_visible_fields(session: AsyncSession, order_id: int, fields: set[str]) -> None:
    """Create or update visibility settings for an order."""
    result = await session.execute(select(OrderVisibility).where(OrderVisibility.order_id == order_id))
    record = result.scalar_one_or_none()
    payload = _normalize_visible_fields(fields)
    if record:
        record.fields = payload
    else:
        record = OrderVisibility(order_id=order_id, fields=payload)
        session.add(record)
    await session.commit()


async def get_master_visible_fields(session: AsyncSession, order_id: int) -> set[str]:
    """Load visibility settings for an order."""
    result = await session.execute(select(OrderVisibility).where(OrderVisibility.order_id == order_id))
    record = result.scalar_one_or_none()
    return _parse_visible_fields(record.fields if record else "")


async def get_order_photo_counts(session: AsyncSession, order_id: int) -> dict[str, int]:
    """Return before/after photo counters for an order."""
    result = await session.execute(select(OrderPhoto.type).where(OrderPhoto.order_id == order_id))
    out = {"before": 0, "after": 0}
    for photo_type in result.scalars().all():
        if photo_type == "after":
            out["after"] += 1
        else:
            out["before"] += 1
    return out


async def get_order_photo_type_count(session: AsyncSession, order_id: int, photo_type: str) -> int:
    """Return count of photos for one order/type."""
    result = await session.execute(
        select(OrderPhoto.id).where(
            OrderPhoto.order_id == order_id,
            OrderPhoto.type == photo_type,
        )
    )
    return len(result.scalars().all())

