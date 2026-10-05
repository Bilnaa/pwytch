from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Counter


async def increment_counter(session: AsyncSession, counter_type: str, key: str):
    increment = 1
    insert_stmt = insert(Counter).values(counter_type=counter_type,key=key, value=increment)
    insert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["counter_type", "key"],
        set_={"value": Counter.value + increment},
    )

    await session.execute(insert_stmt)
    await session.commit()
