"""Bounded, visual-only beginner story runner. Unknown screens stop safely."""
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
import cv2
from module.exception import RequestHumanTakeover, TaskEnd
from module.logger import logger
from module.ocr.models import get_ocr_model
from tasks.BeginnerQuest.vision import template_action, choose_text, ellipsis_action, movie_skip_action, Action

from tasks.BeginnerQuest.search import SceneSearch, click_point

ROOT = Path(__file__).parent


class ScriptTask:
    def __init__(self, config, device):
        self.config, self.device = config, device
        self.options = config.beginner_quest.quest_options
        self.borrow_seen = False
        self.battle_pending = False
        self.skip_pending = False
        self.team_verified = False
        self.selected_role = None
        self.search_allowed = False
        self.search = SceneSearch(self.options.max_search_swipes)

    def templates(self, image, kinds):
        for rule in json.loads((ROOT / 'rules.json').read_text(encoding='utf-8')):
            if rule['kind'] not in kinds:
                continue
            action = template_action(image, Path(rule['file']), rule['kind'],
                                     rule.get('threshold', .86), tuple(rule['region']))
            if action:
                if 'click_point' in rule:
                    action.point = tuple(rule['click_point'])
                return action
        return None

    def decide(self, image):
        self.search_allowed = False
        movie = movie_skip_action(image)
        if movie:
            self.skip_pending = True
            return movie
        combat = self.templates(image, {'wait_battle'})
        if combat:
            return combat
        boxes = get_ocr_model().detect_and_ocr(image)
        # Positive story HUD plus an empty text area: never pan dialogues or menus.
        self.search_allowed = bool(self.templates(image, {'search_scene'})) and not any(
            b.ocr_text.strip() and float(b.box[:, 1].mean()) > 130 for b in boxes)

        # A run can stop after opening this modal; explicit skip wording is safe
        # to resume without the previous process's transient skip_pending flag.
        confirm_skip = choose_text(boxes, ('确认跳过',), (550, 330, 1000, 550), 'confirm_skip')
        if confirm_skip:
            self.skip_pending = False
            return confirm_skip
        if any('剧情简介' in b.ocr_text for b in boxes):
            return None
        if any('个性化内容推荐' in b.ocr_text for b in boxes):
            return choose_text(boxes, ('关闭个性化推荐',), (200, 500, 700, 720), 'dismiss_recommendation')
        if any('借用' in b.ocr_text and ('可以' in b.ocr_text or '解锁' in b.ocr_text) for b in boxes):
            self.borrow_seen = True
        # Never interpret scrolling chat, account screens or shop labels as quest buttons.
        blockers = ('体力不足', '购买体力', '充值', '再次挑战', '账号登录', '其他设备登录')
        if any((len(b.ocr_text) <= 16 and any(word in b.ocr_text for word in blockers)) or b.ocr_text == '失败' for b in boxes):
            raise RequestHumanTakeover('BeginnerQuest: resource, login or failed-battle prompt')
        prepare_button = self.templates(image, {'prepare'})
        if prepare_button:
            if self.borrow_seen and self.options.require_verified_team and not self.team_verified:
                raise RequestHumanTakeover('BeginnerQuest: verify borrowed damage dealer and fire provider before battle')
            self.battle_pending = False
            return prepare_button
        if self.battle_pending and self.templates(image, {'search_scene'}):
            logger.info('BeginnerQuest: clear old battle state after return to story/courtyard')
            self.battle_pending = False
        if self.battle_pending:
            result = (self.templates(image, {'reward'}) or choose_text(
                boxes, ('点击屏幕继续', '点击任意位置继续', '领取奖励'),
                (250, 350, 1250, 720), 'reward'))
            if result:
                self.battle_pending = False
                return result
            return Action('wait_battle', (0, 0))
        if (self.templates(image, {'intro_frame_top'})
                and self.templates(image, {'intro_frame_bottom'})):
            return Action('dismiss_intro', (950, 650))
        skip = self.templates(image, {'skip', 'skip_movie', 'dismiss_intro'})
        if skip:
            self.skip_pending = skip.name != 'dismiss_intro'
            return skip
        if self.skip_pending:
            confirm = choose_text(boxes, ('确认跳过', '跳过', '确定'),
                                  (350, 220, 1000, 590), 'confirm_skip')
            self.skip_pending = False
            if confirm:
                return confirm
        skip = (choose_text(boxes, ('跳过', '跳过剧情'), (1000, 0, 1280, 120), 'skip')
                or choose_text(boxes, ('跳过', '跳过剧情'), (650, 400, 1100, 620), 'skip'))
        if skip:
            self.skip_pending = True
            return skip
        borrow = choose_text(boxes, ('前往借用', '借用式神', '借用'),
                             (250, 140, 1250, 700), 'borrow')
        if borrow and self.options.borrow_support:
            self.borrow_seen = True
            return borrow
        # Team templates require separately calibrated cards and on-field markers.
        # Do not infer successful deployment from clicking a card or changing pixels.
        team = self.templates(image, {'support_on_field', 'fire_on_field'})
        if team:
            self.team_verified = self.team_is_verified(image)
        if self.borrow_seen and not self.team_verified:
            names = ((self.options.fire_provider,) if self.templates(image, {'support_on_field'})
                     else tuple(self.options.preferred_support.split(',')))
            support = choose_text(boxes, names,
                                  (180, 140, 1250, 700), 'select_support')
            if support:
                support.name = 'select_fire' if names == (self.options.fire_provider,) else 'select_support'
                self.selected_role = support.name
                return support
            equip = choose_text(boxes, ('上阵', '使用该式神'), (600, 300, 1280, 720), 'equip_support')
            if equip:
                return equip
        ready = choose_text(boxes, ('准备',), (1000, 450, 1280, 720), 'prepare')
        if ready:
            if self.borrow_seen and self.options.require_verified_team and not self.team_verified:
                raise RequestHumanTakeover('BeginnerQuest: verify borrowed damage dealer and fire provider before battle')
            return ready
        for words, region, name in [
            (('点击屏幕继续', '点击任意位置继续', '点击空白处关闭'), (250, 500, 1200, 720), 'continue'),
            (('探查', '调查'), (100, 120, 1200, 650), 'investigate'),
            (('领取', '领取奖励'), (450, 350, 1150, 700), 'reward'),
        ]:
            action = choose_text(boxes, words, region, name)
            if action:
                return action
        npc = (ellipsis_action(image) or self.templates(image, {'talk'})) if self.templates(image, {'search_scene'}) else None
        return npc or self.templates(image, {'investigate', 'fight', 'quest', 'reward'})

    def scene_is_ready(self, image):
        # Loose ellipsis/skip matches can occur inside promotional movies.
        return bool(self.templates(image, {'search_scene', 'wait_battle', 'dismiss_intro'})
                    or (self.templates(image, {'intro_frame_top'})
                        and self.templates(image, {'intro_frame_bottom'})))

    def team_is_verified(self, image):
        return all(self.templates(image, {kind}) is not None
                   for kind in ('support_on_field', 'fire_on_field'))

    def run(self):
        started = last_action = time.monotonic()
        last_key, repeats, battles, count = None, 0, 0, 0
        diagnostic = Path('log/beginner_quest') / self.config.config_name
        diagnostic.mkdir(parents=True, exist_ok=True)
        state_file = diagnostic / 'state.json'
        if state_file.exists():
            state = json.loads(state_file.read_text())
            self.borrow_seen = bool(state.get('borrow_seen', False))
            self.battle_pending = bool(state.get('battle_pending', False))
        initial = self.device.screenshot()
        if (getattr(self.device, 'is_desktop', False)
                and not self.device.find_desktop_login_popup() and self.scene_is_ready(initial)):
            self.device.desktop_mark_logged_in()
        self.device.stuck_record_clear()
        while count < self.options.max_actions and time.monotonic() - started < self.options.max_seconds:
            image = self.device.screenshot()
            action = self.decide(image)
            state_file.write_text(json.dumps({'borrow_seen': self.borrow_seen, 'battle_pending': self.battle_pending}))
            if not action:
                if (self.options.search_npc and self.search_allowed
                        and time.monotonic() - last_action > 3):
                    drag = self.search.next_drag(image)
                    if drag is None:
                        cv2.imwrite(str(diagnostic / 'unrecognized.png'), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                        raise RequestHumanTakeover('BeginnerQuest: bounded NPC search exhausted')
                    logger.info('BeginnerQuest search %s/%s: %s', self.search.count, self.search.limit, drag)
                    if self.options.dry_run:
                        break
                    self.device.swipe(*drag, control_name='BeginnerQuest_search')
                    self.device.stuck_record_clear()
                    count += 1
                    last_action = time.monotonic()
                    time.sleep(random.uniform(1.2, 1.8))
                    continue
                if time.monotonic() - last_action > self.options.idle_seconds:
                    cv2.imwrite(str(diagnostic / 'unrecognized.png'), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                    raise RequestHumanTakeover('BeginnerQuest: no recognized interaction; saved unrecognized.png')
                time.sleep(1)
                continue
            if action.name == 'wait_battle':
                last_action = time.monotonic()
                self.device.stuck_record_clear()
                time.sleep(2)
                continue
            self.search.reset()
            key = (action.name, action.point[0] // 15, action.point[1] // 15)
            repeats = repeats + 1 if key == last_key else 0
            if repeats >= 4:
                cv2.imwrite(str(diagnostic / 'unrecognized.png'), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                raise RequestHumanTakeover('BeginnerQuest: repeated interaction without progress')
            if action.name in ('fight', 'prepare'):
                if battles >= self.options.max_battles:
                    break
                battles += 1
            logger.info('BeginnerQuest action=%s point=%s confidence=%.3f',
                        action.name, action.point, action.score)
            if self.options.dry_run:
                break
            self.device.click(*click_point(action.point, self.options.click_jitter), control_check=False, control_name='BeginnerQuest_' + action.name)
            if action.name == 'prepare':
                self.battle_pending = True
                state_file.write_text(json.dumps({'borrow_seen': self.borrow_seen, 'battle_pending': True}))
            self.device.stuck_record_clear()
            count += 1
            last_key, last_action = key, time.monotonic()
            time.sleep(random.uniform(.9, 1.5))
        self.config.beginner_quest.scheduler.next_run = datetime.now() + timedelta(hours=1)
        self.config.save()
        raise TaskEnd('BeginnerQuest bounded run finished; story completion is not asserted')
