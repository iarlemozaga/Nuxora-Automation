from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    discord_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    avatar = Column(String)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Guild(Base):
    __tablename__ = "guilds"

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, unique=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    icon = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, unique=True)

    allowlist_title = Column(Text, default="")
    allowlist_description = Column(Text, default="")
    allowlist_footer = Column(Text, default="")
    allowlist_questions = Column(Text, default="[]")
    allowlist_answer_role_mappings = Column(Text, default="[]")

    allowlist_category_id = Column(String, default="")

    staff_channel_id = Column(String, default="")
    suggestion_channel_id = Column(String, default="")

    approved_role_id = Column(String, default="")
    remove_role_on_approved_id = Column(String, default="")
    interview_role_id = Column(String, default="")

    approved_channel_id = Column(String, default="")
    rejected_channel_id = Column(String, default="")

    autorole_role_id = Column(String, default="")

    ticket_panel_title = Column(Text, default="")
    ticket_panel_description = Column(Text, default="")
    ticket_panel_footer = Column(Text, default="")

    ticket_category_id = Column(String, default="")
    ticket_staff_role_id = Column(String, default="")
    logs_channel_id = Column(String, default="")

    ticket_types = Column(Text, default="[]")

    member_join_channel_id = Column(String, default="")
    member_leave_channel_id = Column(String, default="")

    member_join_title = Column(Text, default="")
    member_join_description = Column(Text, default="")
    member_join_footer = Column(Text, default="")
    member_join_color = Column(String, default="#8B0000")

    member_leave_title = Column(Text, default="")
    member_leave_description = Column(Text, default="")
    member_leave_footer = Column(Text, default="")
    member_leave_color = Column(String, default="#8B0000")
