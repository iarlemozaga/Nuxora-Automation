from database.db import SessionLocal
from database.models import GuildSettings
from fastapi import APIRouter

router = APIRouter(prefix="/settings")


@router.get("/{guild_id}")
def get_settings(guild_id: str):
    db = SessionLocal()

    settings = db.query(GuildSettings).filter_by(guild_id=guild_id).first()

    return settings
