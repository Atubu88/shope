from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_get_user

async def check_salon_access(session: AsyncSession, user_id: int, salon_id: int) -> bool:
    """Return True if user has access to salon."""
    user = await orm_get_user(session, user_id)
    if not user:
        return False
    if user.is_super_admin:
        return True
    return user.salon_id == salon_id