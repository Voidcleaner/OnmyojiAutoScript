"""Small progression planner that dispatches existing OAS tasks in short batches.

The on-screen novice requirements override community guides. No external code is
loaded by this module, and failed objectives need a changed build before retry.
"""
from dataclasses import dataclass, field
import importlib
import re
from datetime import time
from module.exception import TaskEnd, RequestHumanTakeover

NUMBERS = dict(zip('一二三四五六七八九', range(1, 10)))
NUMBERS.update(dict(zip('壹贰叁肆伍陆柒捌玖', range(1, 10))))


def number(text):
    if text.isdigit():
        return int(text)
    text = text.replace('拾', '十')
    if '十' in text:
        a,b = text.split('十',1)
        return NUMBERS.get(a,1)*10 + NUMBERS.get(b,0)
    return NUMBERS.get(text)


@dataclass(frozen=True)
class Objective:
    kind: str
    target: int | None
    text: str

    @property
    def key(self):
        return f'{self.kind}:{self.target}'


def parse_objective(text):
    text = text.replace(' ', '')
    # Layer comes ONLY from the suffix, never from 八岐大蛇's name.
    layer = re.search(r'(?:御魂|觉醒)[·・:：]([一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾\d]+)层', text)
    if layer:
        return Objective('orochi' if '御魂' in layer[0] else 'awakening', number(layer[1]), text)
    chapter = re.search(r'第([一二三四五六七八九十\d]+)章', text)
    if chapter:
        return Objective('story' if any(w in text for w in ('故事','剧情')) else 'exploration_hard' if '困难' in text else 'exploration', number(chapter[1]), text)
    level = re.search(r'(?:达成|达到|至)(\d+)级', text)
    if level:
        return Objective('soul_upgrade' if '御魂' in text else 'shikigami_upgrade' if '式神' in text else 'player_level', int(level[1]), text)
    if '经验妖怪' in text:
        return Objective('experience', None, text)
    if '石距' in text:
        return Objective('tako', None, text)
    return None


@dataclass
class Snapshot:
    player_level: int
    requirements: list[Objective] = field(default_factory=list)
    unclaimed_rewards: bool = False
    story_available: bool = False
    unlocked_chapter: int = 1
    cleared_chapter: int = 1
    experience_available: bool = False
    tako_available: bool = False
    build_revision: str = 'initial'
    failures: dict[str,str] = field(default_factory=dict)
    deferred_modules: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ModulePlan:
    module: str
    target: int | None = None
    reason: str = ''
    requires_teammate: bool = False


def choose_plan(state, target_level=40):
    if state.player_level >= target_level:
        return ModulePlan('Complete', target_level, 'Target level verified')
    if state.unclaimed_rewards:
        return ModulePlan('ClaimNoviceRewards', reason='Free rewards first')
    eligible = [o for o in state.requirements if state.failures.get(o.key) != state.build_revision]
    # Explicit story objectives unlock subsequent content before repeat farming.
    for objective in eligible:
        if objective.kind == 'story':
            return ModulePlan('BeginnerQuest', objective.target, objective.text)
    # Only dispatch party runs when availability was verified in the UI.
    if state.player_level >= 15 and state.experience_available and 'ExperienceYoukai' not in state.deferred_modules:
        return ModulePlan('ExperienceYoukai', reason='Available hosted character-XP run', requires_teammate=True)
    if state.player_level >= 15 and state.tako_available and 'Tako' not in state.deferred_modules:
        return ModulePlan('Tako', reason='Available hosted character-XP run', requires_teammate=True)
    for objective in eligible:
        if objective.kind == 'orochi':
            return ModulePlan('Orochi', objective.target, objective.text)
        if objective.kind == 'awakening':
            return ModulePlan('AwakeningAdapter', objective.target, objective.text)
    if state.story_available:
        return ModulePlan('BeginnerQuest', reason='Available story before repeated farming')
    for objective in eligible:
        if objective.kind.startswith('exploration') and objective.target <= state.unlocked_chapter:
            return ModulePlan('ExplorationHardAdapter' if objective.kind=='exploration_hard' else 'Exploration', objective.target, objective.text)
        if objective.kind.endswith('_upgrade'):
            return ModulePlan('BuildAdapter', objective.target, objective.text)
    # Never jump to a locked guide chapter or repeatedly retry a failed boss.
    chapter = max(1, min(state.unlocked_chapter, state.cleared_chapter + 1))
    if state.failures.get(f'exploration:{chapter}') == state.build_revision:
        chapter = max(1,state.cleared_chapter)
    return ModulePlan('Exploration', chapter, 'Short XP batch, then re-read level and novice tasks')


def run_existing(plan, config, device, *, build_revision='initial', xp_only=False):
    """Reuse the same Device and OAS modules; completion still needs UI verification."""
    if plan.module == 'BeginnerQuest':
        from tasks.BeginnerQuest.story import StoryRunner
        return StoryRunner(config,device).run_chapter(plan.target)
    if plan.module == 'Orochi' and plan.target is not None and 1<=plan.target<=7:
        from tasks.BeginnerQuest.awakening import OrochiNoviceAdapter
        return OrochiNoviceAdapter(config,device).run_to(plan.target,build_revision=build_revision)
    if plan.module == 'AwakeningAdapter':
        from tasks.BeginnerQuest.awakening import AwakeningAdapter
        return AwakeningAdapter(config,device).run_to(plan.target,build_revision=build_revision)
    allowed = {'Orochi','Exploration','ExplorationHardAdapter','ExperienceYoukai','GoldYoukai','Tako'}
    if plan.module not in allowed:
        raise ValueError('This plan requires a novice UI adapter')
    if plan.module == 'Orochi' and (plan.target is None or not 1 <= plan.target <= 13):
        raise ValueError('Unsupported soul layer')
    if plan.module in {'Exploration','ExplorationHardAdapter'} and (plan.target is None or not 1 <= plan.target <= 28):
        raise ValueError('Unsupported exploration chapter')
    changed = []
    def override(obj, key, value):
        changed.append((obj,key,getattr(obj,key)));setattr(obj,key,value)
    if plan.module == 'Orochi':
        from tasks.Orochi.config import UserStatus, Layer
        c=config.orochi.orochi_config
        override(c,'user_status',UserStatus.ALONE)
        override(c,'layer',list(Layer)[plan.target-1])
        override(c,'limit_count',1)
        override(c,'limit_time',time(0,5))
    elif plan.module in {'Exploration','ExplorationHardAdapter'}:
        from tasks.Exploration.config import UserStatus,ExplorationLevel,UpType,AutoRotate
        c=config.exploration.exploration_config
        override(c,'user_status',UserStatus.ALONE)
        override(c,'exploration_level',list(ExplorationLevel)[plan.target-1])
        override(c,'minions_cnt',3)
        override(c,'limit_time',time(0,5))
        override(c,'up_type',UpType.EXP if xp_only else UpType.ALL)
        override(c,'auto_rotate',AutoRotate.no)
    try:
        if plan.module in {'Exploration','ExplorationHardAdapter'}:
            from tasks.BeginnerQuest.exploration_hard import ExplorationHardAdapter,ExplorationNormalAdapter
            handler=(ExplorationHardAdapter if plan.module=='ExplorationHardAdapter' else ExplorationNormalAdapter)(config,device)
        else:
            handler=importlib.import_module(f'tasks.{plan.module}.script_task').ScriptTask(config,device)
        if plan.module in {'Exploration','ExplorationHardAdapter'}:
            handler.progression_boss_wins=0
            original_fire=handler.fire
            def record_boss_fire(button):
                result=original_fire(button)
                if result and button is handler.I_BOSS_BATTLE_BUTTON:
                    handler.progression_boss_wins+=1
                return result
            handler.fire=record_boss_fire
        original=handler.battle_wait
        def stop_on_loss(*args,**kwargs):
            result=original(*args,**kwargs)
            if result is False:
                raise RequestHumanTakeover(f'Progression battle lost in {plan.module}; review roster/souls before retry')
            return result
        handler.battle_wait=stop_on_loss
        try:handler.run()
        except TaskEnd:pass
    finally:
        for obj,key,value in reversed(changed):setattr(obj,key,value)
        config.save()
    if plan.module in {'Exploration','ExplorationHardAdapter'}:
        return {'boss_wins':handler.progression_boss_wins,'chapter':plan.target,
                'difficulty':'hard' if plan.module=='ExplorationHardAdapter' else 'normal'}
    return getattr(handler, 'progression_outcome', 'verify_in_novice_ui')


def read_player_level(image):
    """Read only the avatar's level diamond, never shikigami or handbook levels."""
    import cv2
    from module.ocr.models import get_ocr_model
    crop=cv2.resize(image[:65,:65],None,fx=4,fy=4)
    values=[int(b.ocr_text) for b in get_ocr_model().detect_and_ocr(crop)
            if b.score >= .7 and re.fullmatch(r'\d{1,2}',b.ocr_text) and 1 <= int(b.ocr_text) <= 60]
    return values[0] if len(values)==1 else None
