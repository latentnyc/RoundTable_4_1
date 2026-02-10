from sqlalchemy import (
    MetaData, Table, Column, String, Integer, Boolean, DateTime, Text, ForeignKey
)
from sqlalchemy.sql import func

metadata = MetaData()

# PROFILES
profiles = Table(
    "profiles",
    metadata,
    Column("id", String, primary_key=True),
    Column("username", String, unique=True, nullable=False),
    Column("api_key", String, nullable=True),
    Column("llm_provider", String, server_default="Gemini"),
    Column("is_admin", Boolean, server_default="0"),
    Column("status", String, server_default="interested"),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

# CAMPAIGNS
campaigns = Table(
    "campaigns",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("gm_id", String, ForeignKey("profiles.id"), nullable=False),
    Column("status", String, server_default="active"),
    Column("api_key", String, nullable=True),
    Column("api_key_verified", Boolean, server_default="0"),
    Column("model", String, nullable=True),
    Column("system_prompt", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

# CHARACTERS
characters = Table(
    "characters",
    metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, ForeignKey("profiles.id"), nullable=False),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=True),
    Column("name", String, nullable=False),
    Column("role", String, nullable=False), # Class
    Column("race", String, server_default="Human"),
    Column("level", Integer, server_default="1"),
    Column("xp", Integer, server_default="0"),
    Column("sheet_data", Text, nullable=False), 
    Column("backstory", Text, nullable=True),
    Column("control_mode", String, server_default="human"),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

# GAME STATES
game_states = Table(
    "game_states",
    metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("turn_index", Integer, server_default="0"),
    Column("phase", String, server_default="exploration"),
    Column("state_data", Text, nullable=False), 
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
)

# CHAT MESSAGES
chat_messages = Table(
    "chat_messages",
    metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("sender_id", String, nullable=False),
    Column("sender_name", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("is_tool_output", Boolean, server_default="0"),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

# COMPENDIUM TABLES
def define_compendium_table(name):
    return Table(
        name,
        metadata,
        Column("id", String, primary_key=True),
        Column("name", String, nullable=False),
        Column("data", Text, nullable=False)
    )

spells = Table(
    "spells",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("level", Integer, nullable=True),
    Column("school", String, nullable=True),
    Column("data", Text, nullable=False)
)

monsters = Table(
    "monsters",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("type", String, nullable=True),
    Column("cr", String, nullable=True),
    Column("data", Text, nullable=False)
)

items = Table(
    "items",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("type", String, nullable=True),
    Column("data", Text, nullable=False)
)

classes = define_compendium_table("classes")
races = define_compendium_table("races")
alignments = define_compendium_table("alignments")
feats = define_compendium_table("feats")
subraces = define_compendium_table("subraces")
backgrounds = define_compendium_table("backgrounds")
