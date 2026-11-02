"""Observe novice requirements and close/claim verified reward panels via OAS."""
from dataclasses import dataclass,field
import re
import time
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.BeginnerQuest.planner import parse_objective,number,read_player_level
from tasks.BeginnerQuest.vision import choose_text
from module.ocr.models import get_ocr_model
from module.exception import RequestHumanTakeover


@dataclass
class HubObservation:
    stage: int | None = None
    progress: tuple | None = None
    handbook_level: int | None = None
    objectives: list = field(default_factory=list)
    unsupported: list = field(default_factory=list)


def observe_tasks(boxes):
    out=HubObservation()
    items=[(b.ocr_text.replace(' ',''),*b.box.mean(axis=0)) for b in boxes if b.score>=.65]
    for text,x,y in items:
        if 200<x<450 and 230<y<330:
            match=re.search(r'阶段[·.:：]?([一二三四五六七八九十]+)',text)
            if match:out.stage=number(match[1])
        match=re.fullmatch(r'(\d+)/(\d+)',text)
        if match and 200<x<450:
            if 330<y<400:out.progress=tuple(map(int,match.groups()))
            elif 130<y<180 and int(match[2])==60:out.handbook_level=int(match[1])
    for text,x,y in items:
        if text!='前往' or not (1030<x<1180 and 220<y<635):continue
        row=sorted(((ty,tx,t) for t,tx,ty in items if 480<tx<910 and abs(ty-y)<45))
        description=''.join(t for _,_,t in row)
        goal=parse_objective(description)
        if goal:out.objectives.append(goal)
        else:out.unsupported.append(description)
    return out


class NoviceHub(GameUi):
    """Bounded menu adapter; no shop unlocking, sharing, or paid rewards."""
    def _read(self):
        self.screenshot()
        return get_ocr_model().detect_and_ocr(self.device.image)

    def _tap(self,point):
        self.device.click(*point,control_check=False,control_name='NOVICE_HUB')
        time.sleep(.8)
        return self._read()

    def _dismiss(self,boxes):
        from tasks.Component.phone_prompt import handle_phone_prompt
        if handle_phone_prompt(self):
            return True
        if self.appear_then_click(GlobalGameAssets.I_UI_CLOSE_CELEBRATION,interval=.6):
            time.sleep(.7)
            return True
        words=[b.ocr_text.replace(' ','') for b in boxes]
        if '获得奖励' in words:
            self._tap((1100,600))
            return True
        action=choose_text(boxes,('点击屏幕继续','点击空白处关闭','点击任意位置继续'),(200,500,1250,720),'continue')
        if action:
            self._tap(action.point)
            return True
        return False

    def _clear_completion(self):
        for _ in range(6):
            boxes=self._read()
            if not self._dismiss(boxes):return boxes
        raise RequestHumanTakeover('Novice reward panel did not close after bounded attempts')

    def _claim_visible(self):
        for _ in range(4):
            boxes=self._clear_completion()
            # The free one-key flag is in the bottom-right margin. Paid unlocks
            # are at the top and never enter this selection region.
            words=[b.ocr_text.replace(' ','') for b in boxes
                   if b.box[:,0].mean()>1170 and 520<b.box[:,1].mean()<650]
            if not (any('键' in t for t in words) and any('领取' in t for t in words)):
                return boxes
            self._tap((1220,586))
        return self._clear_completion()

    def scan(self):
        self.device.click_record_clear()
        self.goto_page(page_main)
        player_level=read_player_level(self.device.image)
        for _ in range(3):
            boxes=self._tap((300,356))
            if any('初入平安京' in b.ocr_text for b in boxes):break
        else:raise RequestHumanTakeover('Cannot open novice hub from verified courtyard')
        self._tap((100,180))
        self._claim_visible()
        self._tap((1230,295))
        self._claim_visible()
        self._tap((1230,180))
        boxes=self._claim_visible()
        observation=observe_tasks(boxes)
        self.goto_page(page_main)
        return player_level,observation
