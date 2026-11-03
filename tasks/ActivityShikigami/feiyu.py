"""Feiyu Lingyun daily boosted training; reuse OAS preparation and settlement."""
import json
import re
import time
from pathlib import Path
from module.exception import RequestHumanTakeover
from module.atom.image import RuleImage
from tasks.BeginnerQuest.novice_hub import NoviceHub
from tasks.BeginnerQuest.vision import choose_text
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig


def boosted_count(boxes):
    for b in boxes:
        if b.score < .7:
            continue
        text=b.ocr_text.replace(' ','')
        if '掉落提升' in text or '挑战掉落' in text:
            match=re.search(r'([0-5])/5',text)
            if match:
                return int(match[1])
    return None


class FeiyuTraining(NoviceHub,GeneralBattle):
    COST6 = RuleImage(roi_front=(1135,625,45,30),roi_back=(1100,610,100,70),threshold=.88,
                      method="Template matching",file="./tasks/ActivityShikigami/as/feiyu_cost6.png")
    def _save(self,status,**values):
        path=Path('log/feiyu')/self.config.config_name/'training.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        state={'status':status,**values}
        path.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
        print('FEIYU_TRAINING',json.dumps(state,ensure_ascii=False),flush=True)
        return state

    def on_battle_failed(self):
        self._save('lost')
        raise RequestHumanTakeover('Feiyu training lost; inspect formation before retry')

    def run_boosted(self,max_runs=5):
        if not 1<=max_runs<=5:
            raise ValueError('Daily boosted training budget must be 1..5')
        wins=0
        for _ in range(max_runs):
            boxes=self._clear_completion()
            title=choose_text(boxes,('赛事训练',),(100,0,350,85),'training_title')
            count=boosted_count(boxes)
            if not title or count is None:
                raise RequestHumanTakeover('Current event training page/daily counter not verified')
            if count>=5:
                return self._save('daily_complete',verified_count=count,wins=wins)
            challenge=choose_text(boxes,('挑战',),(1080,560,1270,650),'FEIYU_CHALLENGE')
            cost=any(re.fullmatch(r'[xX×]?30',b.ocr_text.replace(' ',''))
                     and b.score>=.7 and b.box[:,0].mean()>1120 and 630<b.box[:,1].mean()<675 for b in boxes)
            if not challenge or not cost:
                raise RequestHumanTakeover('Expected 30 stamina challenge not verified')
            self._save('entering',verified_count=count,wins=wins)
            self._tap(challenge.point)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                self.screenshot()
                if self.is_in_prepare(False) or self.is_in_real_battle(False):
                    break
                time.sleep(.5)
            else:
                raise RequestHumanTakeover('Training battle did not start; do not replay challenge')
            if not self.run_general_battle(GeneralBattleConfig()):
                self.on_battle_failed()
            wins+=1
            # Settlement may need time to return to the training counter.
            for _ in range(15):
                boxes=self._clear_completion()
                after=boosted_count(boxes)
                if after is not None and after>count:
                    break
                time.sleep(1)
            else:
                raise RequestHumanTakeover('Training win observed but daily counter did not advance')
            self._save('won',verified_count=after,wins=wins)
            if after>=5:
                return self._save('daily_complete',verified_count=after,wins=wins)
        return self._save('batch_limit',verified_count=after,wins=wins)

    def run_event_battle(self):
        """One inspected six-stamina racer duel; never guess other event costs."""
        import cv2
        from module.ocr.models import get_ocr_model
        boxes=self._read()
        text=''.join(b.ocr_text.replace(' ','') for b in boxes)
        if '赛车对决' not in text or '事件描述' not in text:
            raise RequestHumanTakeover('Racer duel panel not verified')
        crop=cv2.resize(self.device.image[620:665,1090:1210],None,fx=4,fy=4)
        costs=[int(m.group(1)) for b in get_ocr_model().detect_and_ocr(crop)
               if b.score>=.7 and (m:=re.fullmatch(r'[xX×]?(\d+)',b.ocr_text.replace(' ','')))]
        if costs!=[6] and not self.appear(self.COST6):
            raise RequestHumanTakeover(f'Expected six-stamina event cost, observed {costs}')
        action=choose_text(boxes,('挑战',),(1050,550,1250,640),'FEIYU_EVENT_CHALLENGE')
        if not action:raise RequestHumanTakeover('Event challenge not verified')
        self._tap(action.point)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            self.screenshot()
            if self.is_in_prepare(False) or self.is_in_real_battle(False):break
            time.sleep(.5)
        else:raise RequestHumanTakeover('Event battle entry unverified')
        if not self.run_general_battle(GeneralBattleConfig()):self.on_battle_failed()
        return {'status':'won','cost':6}

    def _settled_map_boxes(self):
        previous=None;stable=0
        for _ in range(15):
            boxes=self._clear_completion()
            text=''.join(b.ocr_text.replace(' ','') for b in boxes)
            nodes=sorted(tuple(map(int,b.box.mean(axis=0))) for b in boxes
                         if b.ocr_text.replace(' ','')=='赛车对决' and b.box[:,0].mean()>320)
            if '探索进度' in text and previous is not None and len(nodes)==len(previous) and all(
                    abs(x-px)<8 and abs(y-py)<8 for (x,y),(px,py) in zip(nodes,previous)):
                stable+=1
                if stable>=2:return boxes
            else:stable=0
            previous=nodes if '探索进度' in text else None
            time.sleep(.7)
        raise RequestHumanTakeover('Exploration camera did not settle; no map click sent')

    def run_map_duels(self,max_events=28):
        if not 1<=max_events<=28:raise ValueError('Invalid map event budget')
        for step in range(max_events):
            boxes=self._settled_map_boxes()
            progress=next((tuple(map(int,m.groups())) for b in boxes
                           if (m:=re.search(r'探索进度(\d+)/(\d+)',b.ocr_text.replace(' ','')))),None)
            if progress is None:raise RequestHumanTakeover('Exploration map progress not verified')
            if progress[0]>=progress[1]:
                return {'status':'map_complete','progress':progress}
            nodes=[b for b in boxes if b.score>=.75 and b.ocr_text.replace(' ','')=='赛车对决'
                   and 320<b.box[:,0].mean()<1200 and 100<b.box[:,1].mean()<620]
            if not nodes:
                return {'status':'story_node_required','progress':progress}
            node=nodes[0];x,y=map(int,node.box.mean(axis=0))
            self._tap((x,y-40))
            result=self.run_event_battle()
            after=None
            for _ in range(15):
                boxes=self._clear_completion()
                after=next((tuple(map(int,m.groups())) for b in boxes
                            if (m:=re.search(r'探索进度(\d+)/(\d+)',b.ocr_text.replace(' ','')))),None)
                if after and after[0]>progress[0]:break
                time.sleep(1)
            else:raise RequestHumanTakeover('Map event won without verified exploration progress')
            print('FEIYU_MAP',json.dumps({'before':progress,'after':after,'battle':result}),flush=True)
        return {'status':'batch_limit','progress':after}
