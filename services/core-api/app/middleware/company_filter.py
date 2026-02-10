import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.broker_client import BrokerClient
from app.models.company import Company


async def get_accessible_company_ids(
    user: User, db: AsyncSession
) -> list[uuid.UUID]:
    """Return list of company IDs that the user is allowed to access.

    - admin: all companies
    - broker: own company + all active client companies
    - other roles: only own company
    """
    if user.role == UserRole.ADMIN.value:
        result = await db.execute(select(Company.id))
        return list(result.scalars().all())

    if user.role == UserRole.BROKER.value:
        company_ids: list[uuid.UUID] = []
        if user.company_id:
            company_ids.append(user.company_id)
        # Fetch active client companies for this broker
        result = await db.execute(
            select(BrokerClient.client_company_id).where(
                BrokerClient.broker_company_id == user.company_id,
                BrokerClient.is_active == True,  # noqa: E712
            )
        )
        client_ids = list(result.scalars().all())
        company_ids.extend(client_ids)
        return company_ids

    # Default: only own company
    if user.company_id:
        return [user.company_id]
    return []
