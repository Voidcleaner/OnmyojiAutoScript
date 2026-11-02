"""Short novice soul/awakening batches using OAS navigation and battle handling."""
import re
import json
import time
from pathlib import Path
import cv2
from module.exception import RequestHumanTakeover
from module.logger import logger
from module.ocr.models import get_ocr_model
from tasks.BeginnerQuest.planner import number
from tasks.BeginnerQuest.vision import choose_text
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_awake_zones,page_main


class AwakeningAdapter(GameUi,GeneralBattle):
    objective_kind="awakening"
    max_layer=5
    zone_page=page_awake_zones
    zone_point=(200,300)
    menu_title="觉醒材料"
    def _read(self):
        self.screenshot()
        return get_ocr_model().detect_and_ocr(self.device.image)

    def _tap(self,point):
        self.device.click(*point,control_check=False,control_name='NOVICE_LAYER')
        time.sleep(1)
        return self._read()

    def on_battle_failed(self):
        self.failed_layers[f'{self.objective_kind}:{self.current_layer}']=self.build_revision
        self.failure_file.parent.mkdir(parents=True,exist_ok=True)
        self.failure_file.write_text(json.dumps(self.failed_layers),encoding='utf-8')
        raise RequestHumanTakeover('Novice layer lost; failure recorded before dismissal, improve formation before retry')

    def run_to(self,target=5,build_revision='initial'):
        if not 1<=target<=self.max_layer:
            raise ValueError('Target layer exceeds calibrated novice range')
        self.build_revision=build_revision
        self.failure_file=Path('log/beginner_quest')/self.config.config_name/'failures.json'
        self.failed_layers=json.loads(self.failure_file.read_text()) if self.failure_file.exists() else {}
        self.goto_page(self.zone_page)
        boxes=self._tap(self.zone_point) if self.zone_point else self._read()
        lock=cv2.imread(str(Path(__file__).parent/'templates/awakening_lock.png'))
        lock=cv2.cvtColor(lock,cv2.COLOR_BGR2RGB)
        completed=set()
        for _ in range(5):
            if not any(self.menu_title in b.ocr_text and b.box[:,1].mean()<90 for b in boxes):
                raise RequestHumanTakeover('Awakening layer menu not verified')
            rows=[]
            for b in boxes:
                x,y=map(int,b.box.mean(axis=0))
                m=re.search(r'([一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾]+)层',b.ocr_text)
                if not m or not (120<x<230 and 100<y<690):continue
                n=number(m[1])
                crop=self.device.image[max(0,y-22):y+22,90:125]
                locked=cv2.minMaxLoc(cv2.matchTemplate(crop,lock,cv2.TM_CCOEFF_NORMED))[1]>=.88
                if n is not None and n<=target and not locked:rows.append((n,(x,y)))
            if not rows:raise RequestHumanTakeover('No verified unlocked awakening layer in view')
            layer,point=max(rows)
            if layer in completed:raise RequestHumanTakeover('Next awakening layer did not unlock after victory')
            if self.failed_layers.get(f'{self.objective_kind}:{layer}')==self.build_revision:
                raise RequestHumanTakeover('Previously failed novice layer requires a changed formation before retry')
            self.current_layer=layer
            logger.info('Novice %s: selected unlocked layer=%s target=%s',self.menu_title,layer,target)
            boxes=self._tap(point)
            y=point[1]
            selected=self.device.image[y-14:y+15,120:220].astype('float32')
            if ((selected[:,:,0]>selected[:,:,1]*1.5)&(selected[:,:,0]>100)).mean()<.25:
                raise RequestHumanTakeover('Requested layer did not become selected')
            fire=choose_text(boxes,('挑战',),(1080,540,1275,680),'challenge')
            if not fire:raise RequestHumanTakeover('Awakening challenge button not verified')
            self._tap(fire.point)
            if not self.run_general_battle():
                raise RequestHumanTakeover('Awakening lost; review formation and souls before another attempt')
            completed.add(layer)
            if layer==target:
                self.goto_page(page_main)
                return sorted(completed)
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                boxes=self._read()
                if any(self.menu_title in b.ocr_text and b.box[:,1].mean()<90 for b in boxes):break
                from tasks.Component.continue_prompt import handle_continue_prompt
                handle_continue_prompt(self)
                time.sleep(.5)
        raise RequestHumanTakeover('Awakening progression batch exhausted')


class OrochiNoviceAdapter(AwakeningAdapter):
    from tasks.Orochi.page import page_orochi
    objective_kind="orochi"
    max_layer=7
    zone_page=page_orochi
    zone_point=None
    menu_title='御魂'
