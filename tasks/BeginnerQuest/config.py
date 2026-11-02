from pydantic import BaseModel, Field
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class QuestOptions(BaseModel):
    target_player_level: int = Field(default=40, ge=1, le=60)
    max_actions: int = Field(default=80, ge=1, le=2000)
    max_seconds: int = Field(default=600, ge=10, le=7200)
    idle_seconds: int = Field(default=30, ge=5, le=120)
    max_battles: int = Field(default=10, ge=0, le=100)
    borrow_support: bool = True
    preferred_support: str = '待宵姑获鸟,姑获鸟,麓铭大岳丸'
    fire_provider: str = '座敷童子'
    require_verified_team: bool = True
    search_npc: bool = True
    max_search_swipes: int = Field(default=8, ge=1, le=20)
    click_jitter: int = Field(default=2, ge=0, le=4)
    dry_run: bool = False


class BeginnerQuest(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    quest_options: QuestOptions = Field(default_factory=QuestOptions)
