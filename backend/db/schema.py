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


# CAMPAIGN TEMPLATES (Catalog / Scenarios)
campaign_templates = Table(
    "campaign_templates",
    metadata,
    Column("id", String, primary_key=True), # e.g. "adv_001_rats"
    Column("name", String, nullable=False),
    Column("description", Text, nullable=True),
    Column("genre", String, nullable=True),
    Column("config", Text, nullable=True), # JSON: time_config, etc.
    Column("json_path", String, nullable=False), # Path to source JSON
    Column("system_prompt", Text, nullable=True),
    Column("initial_state", Text, nullable=True), # JSON: narratives, quests, timeline
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

# CAMPAIGNS
campaigns = Table(
    "campaigns",
    metadata,
    Column("id", String, primary_key=True),
    Column("template_id", String, ForeignKey("campaign_templates.id"), nullable=True),
    Column("name", String, nullable=False),
    Column("description", Text, nullable=True),
    Column("gm_id", String, ForeignKey("profiles.id"), nullable=False),
    Column("status", String, server_default="active"),
    Column("api_key", String, nullable=True),
    Column("api_key_verified", Boolean, server_default="0"),
    Column("model", String, nullable=True),
    Column("system_prompt", Text, nullable=True),
    Column("total_input_tokens", Integer, server_default="0"),
    Column("total_output_tokens", Integer, server_default="0"),
    Column("query_count", Integer, server_default="0"),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

# DEBUG LOGS
debug_logs = Table(
    "debug_logs",
    metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("type", String, nullable=False),
    Column("content", Text, nullable=True),
    Column("full_content", Text, nullable=True),
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

# CAMPAIGN PARTICIPANTS
campaign_participants = Table(
    "campaign_participants",
    metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("user_id", String, ForeignKey("profiles.id"), nullable=False),
    Column("role", String, nullable=False), # 'gm', 'player'
    Column("status", String, server_default="interested"), # 'active', 'interested', 'banned'
    Column("joined_at", DateTime(timezone=True), server_default=func.now())
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

# CAMPAIGN MEMORIES
campaign_memories = Table(
    "campaign_memories",
    metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("summary_text", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

# SCOPED GAME DATA (Instances)
npcs = Table(
    "npcs",
    metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("source_id", String, nullable=True), # Original JSON ID
    Column("name", String, nullable=False),
    Column("role", String, nullable=True),
    Column("data", Text, nullable=False) # JSON: stats, voice, secrets
)

locations = Table(
    "locations",
    metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("source_id", String, nullable=True), # Original JSON ID
    Column("name", String, nullable=False),
    Column("data", Text, nullable=False) # JSON: description, connections, secrets
)

quests = Table(
    "quests",
    metadata,
    Column("id", String, primary_key=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=False),
    Column("source_id", String, nullable=True), # Original JSON ID
    Column("title", String, nullable=False),
    Column("steps", Text, nullable=True), # JSON array
    Column("rewards", Text, nullable=True), # JSON array
    Column("data", Text, nullable=True) # Full JSON object
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
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=True),
    Column("template_id", String, ForeignKey("campaign_templates.id"), nullable=True),
    Column("name", String, nullable=False),
    Column("level", Integer, nullable=True),
    Column("school", String, nullable=True),
    Column("data", Text, nullable=False)
)

monsters = Table(
    "monsters",
    metadata,
    Column("id", String, primary_key=True),
    Column("template_id", String, ForeignKey("campaign_templates.id"), nullable=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=True),
    Column("name", String, nullable=False),
    Column("type", String, nullable=True),
    Column("cr", String, nullable=True),
    Column("data", Text, nullable=False)
)

items = Table(
    "items",
    metadata,
    Column("id", String, primary_key=True),
    Column("template_id", String, ForeignKey("campaign_templates.id"), nullable=True),
    Column("campaign_id", String, ForeignKey("campaigns.id"), nullable=True),
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
