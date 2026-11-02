"""Bounded player-level farming using existing OAS exploration and fresh UI checks."""
import json
import cv2
import re
import time
from pathlib import Path
from module.exception import RequestHumanTakeover
from module.ocr.models import get_ocr_model
from tasks.BeginnerQuest.novice_hub import NoviceHub
from tasks.BeginnerQuest.planner import read_player_level,run_existing,ModulePlan
from tasks.GameUi.page import page_main


def read_stamina(image):
    crop=cv2.resize(image[5:65,875:1040],None,fx=4,fy=4)
    values=[int(b.ocr_text.replace(' ','').rstrip('+')) for b in get_ocr_model().detect_and_ocr(crop)
            if b.score>=.7 and re.fullmatch(r'\d+\+?',b.ocr_text.replace(' ',''))]
    return values[0] if len(values)==1 else None


class LevelingRunner(NoviceHub):
    def run_to(self,chapter,target=40,max_batches=30,min_stamina=60,unchanged_limit=3,xp_only=True):
        if not 1<=chapter<=28 or not 1<=target<=60:raise ValueError('Unsupported chapter/player-level target')
        root=Path('log/beginner_quest')/self.config.config_name
        root.mkdir(parents=True,exist_ok=True)
        started=time.monotonic()
        previous_level=None;unchanged=0
        for batch in range(max_batches+1):
            self.goto_page(page_main)
            self.screenshot()
            level=read_player_level(self.device.image);stamina=read_stamina(self.device.image)
            unchanged=unchanged+1 if level is not None and level==previous_level else 0
            previous_level=level
            state={'unchanged_batches':unchanged,'player_level':level,'target':target,'stamina':stamina,'chapter':chapter,'batch':batch,'elapsed_seconds':round(time.monotonic()-started)}
            if level is None:status='unverified_ui'
            elif level>=target:status='complete'
            elif stamina is None:status='unverified_ui'
            elif stamina<min_stamina:status='low_stamina'
            elif unchanged_limit and unchanged>=unchanged_limit:status='replan_needed'
            elif batch>=max_batches:status='batch_limit'
            else:status='running'
            state['status']=status
            (root/'leveling.json').write_text(json.dumps(state),encoding='utf-8')
            print('LEVELING_STATE',json.dumps(state),flush=True)
            if status=='unverified_ui':raise RequestHumanTakeover('Player level/stamina not verified; do not keep spending')
            if status!='running':return state
            try:
                run_existing(ModulePlan('Exploration',chapter),self.config,self.device,xp_only=xp_only)
            except Exception as exc:
                state.update(status='stopped_error',reason=f'{type(exc).__name__}: {exc}')
                (root/'leveling.json').write_text(json.dumps(state),encoding='utf-8')
                cv2.imwrite(str(root/'leveling_error.png'),cv2.cvtColor(self.device.image,cv2.COLOR_RGB2BGR))
                raise
        raise AssertionError('Bounded loop exhausted without reporting state')
