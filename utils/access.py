from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.orm_query import orm_get_user_salon


async def check_salon_access(session: AsyncSession, user_id: int, salon_id: int) -> bool:
    """Return True if user has access to the given salon.

    A user may belong to multiple salons through the ``UserSalon`` link table.
    This function checks whether the user is linked to ``salon_id`` or has the
    global super admin flag.
    """
    user_salon = await orm_get_user_salon(session, user_id, salon_id)
    if user_salon:
        return True

    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    return bool(user and user.is_super_admin)