from shared.db import row


async def get_guild_status(guild_id: int | str):
    record = await row(
        """
        SELECT status
        FROM customer_guilds
        WHERE guild_id=?
        LIMIT 1
        """,
        (str(guild_id),),
    )

    if not record:
        return None

    return str(record.get("status") or "").lower()


async def is_guild_linked(guild_id: int | str) -> bool:
    status = await get_guild_status(guild_id)
    return status is not None


async def is_guild_active(guild_id: int | str) -> bool:
    status = await get_guild_status(guild_id)
    return status == "active"


async def is_guild_blocked(guild_id: int | str) -> bool:
    status = await get_guild_status(guild_id)
    return status == "blocked"


async def should_process_guild(guild_id: int | str) -> bool:
    return await is_guild_active(guild_id)
