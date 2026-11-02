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
    def run_to(self,chapter,target=40,max_batches=30,min_stamina=60):
        if not 1<=chapter<=28 or not 1<=target<=60:raise ValueError('Unsupported chapter/player-level target')
        root=Path('log/beginner_quest')/self.config.config_name
        root.mkdir(parents=True,exist_ok=True)
        started=time.monotonic()
        for batch in range(max_batches+1):
            self.goto_page(page_main)
            self.screenshot()
            level=read_player_level(self.device.image);stamina=read_stamina(self.device.image)
            state={'player_level':level,'target':target,'stamina':stamina,'chapter':chapter,'batch':batch,'elapsed_seconds':round(time.monotonic()-started)}
            if level is None or stamina is None:status='unverified_ui'
            elif level>=target:status='complete'
            elif stamina<min_stamina:status='low_stamina'
            elif batch>=max_batches:status='batch_limit'
            else:status='running'
            state['status']=status
            (root/'leveling.json').write_text(json.dumps(state),encoding='utf-8')
            print('LEVELING_STATE',json.dumps(state),flush=True)
            if status=='unverified_ui':raise RequestHumanTakeover('Player level/stamina not verified; do not keep spending')
            if status!='running':return state
            run_existing(ModulePlan('Exploration',chapter),self.config,self.device,xp_only=True)
        raise AssertionError('Bounded loop exhausted without reporting state')
