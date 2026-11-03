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


def next_map_arrow(image):
    import cv2
    import numpy as np
    mask=((image[:,:,0]>190)&(image[:,:,1]>150)&(image[:,:,2]<110)).astype(np.uint8)
    _,_,stats,_=cv2.connectedComponentsWithStats(mask,8)
    candidates=[]
    for x,y,w,h,area in stats[1:]:
        if 320<x<1180 and 110<y<550 and 10<=w<=40 and 24<=h<=65 and area>100:
            candidates.append((int(x+w//2),int(y+h+55)))
    return candidates[0] if len(candidates)==1 else None


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
        """One inspected six-stamina duel or north station; verify the event cost."""
        import cv2
        from module.ocr.models import get_ocr_model
        boxes=self._read()
        text=''.join(b.ocr_text.replace(' ','') for b in boxes)
        if not any(name in text for name in ('赛车对决','北部分站赛','中心分站赛')) or '事件描述' not in text:
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
                         if b.ocr_text.replace(' ','') in {'赛车对决','请求','剧情','主线'}
                         and b.box[:,0].mean()>320 and b.box[:,1].mean()<600)
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

    def clear_event_story(self):
        from tasks.BeginnerQuest.script_task import ScriptTask
        dialog=ScriptTask(self.config,self.device)
        allowed={'skip','skip_movie','confirm_skip','continue','dismiss_intro','reward'}
        for _ in range(40):
            self.screenshot()
            action=dialog.decide(self.device.image)
            if not action or action.name not in allowed:return
            self._tap(action.point)
        raise RequestHumanTakeover('Event dialogue exceeded bounded skip budget')


    def run_exploration(self,max_stages=28):
        if not 1<=max_stages<=28:raise ValueError('Invalid exploration stage budget')
        for _ in range(max_stages):
            self.clear_event_story()
            result=self.run_map_duels()
            path=Path('log/feiyu')/self.config.config_name/'map.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(result),encoding='utf-8')
            if result['status']=='map_complete':return result
            boxes=self._settled_map_boxes()
            requests=[b for b in boxes if b.ocr_text=='请求' and b.box[:,0].mean()>320]
            stories=[b for b in boxes if b.ocr_text=='剧情' and 320<b.box[:,0].mean()<1100 and 100<b.box[:,1].mean()<550]
            stations=[b for b in boxes if b.ocr_text=='主线' and 320<b.box[:,0].mean()<1100 and 100<b.box[:,1].mean()<550]
            nodes=requests or stories or stations
            point=next_map_arrow(self.device.image)
            if point is None:
                if not nodes:return result
                x,y=map(int,nodes[0].box.mean(axis=0))
                point=(x,y-55) if requests else (x+30,y+50)
            self._tap(point)
            panel=self._read()
            if any('事件描述' in b.ocr_text for b in panel):
                self.run_event_battle()
            self.clear_event_story()
        return {'status':'stage_limit'}

    def _event_cosmetic_popup(self,boxes):
        if any(b.ocr_text=='获得' and 250<b.box[:,0].mean()<550 and b.box[:,1].mean()<250 for b in boxes):
            return self._dismiss(boxes)
        if any(b.ocr_text=='成就' for b in boxes):return False
        if any('截图分享' in b.ocr_text for b in boxes):
            if not self._dismiss(boxes):self._tap((640,650))
            return True
        if any(any(word in b.ocr_text for word in ('Q版装扮','获得第','获得插画','头像框','全收集','金收集','风物志','式神风物','缘结')) for b in boxes):
            return self._dismiss(boxes)
        return False

    def claim_event_rewards(self):
        from tasks.Component.optional_prompt import handle_cosmetic_activation
        for _ in range(10):
            boxes=self._read()
            if handle_cosmetic_activation(self,boxes):continue
            if self._event_cosmetic_popup(boxes):continue
            if any('获得奖励' in b.ocr_text for b in boxes):
                self._tap((1100,600));continue
            break
        else:raise RequestHumanTakeover('Event reward intro overlays did not close')
        if not any(b.ocr_text=='每日' for b in boxes):
            if not any('飞驰赛场' in b.ocr_text for b in boxes):
                raise RequestHumanTakeover('Event home/reward page not verified')
            self._tap((222,687))
        observations=[]
        for tab,point in [('daily',(1193,199)),('achievements',(1193,346))]:
            self._tap(point)
            for _ in range(3):
                boxes=self._read()
                if not any('飞羽凌云' in b.ocr_text and b.box[:,1].mean()<80 for b in boxes):
                    raise RequestHumanTakeover('Event reward page title not verified')
                if not any(b.ocr_text=='成就' for b in boxes):
                    raise RequestHumanTakeover('Persistent reward tabs not verified')
                claim=choose_text(boxes,('领取',),(1170,530,1270,650),'FEIYU_FREE_CLAIM')
                if not claim:break
                self._tap(claim.point)
                # The reward sheet itself has a persistent pink close button.
                # Dismiss only an explicit gained-reward overlay, never that X.
                for _ in range(10):
                    boxes=self._read()
                    if any('获得奖励' in b.ocr_text for b in boxes):
                        self._tap((1100,600));continue
                    from tasks.Component.optional_prompt import handle_cosmetic_activation
                    if handle_cosmetic_activation(self,boxes):continue
                    if self._event_cosmetic_popup(boxes):continue
                    if any(b.ocr_text=='成就' for b in boxes):break
                    action=choose_text(boxes,('点击屏幕继续','点击任意位置关闭','点击任意位置继续'),
                                       (200,400,1250,720),'FEIYU_REWARD_CONTINUE')
                    if action:self._tap(action.point)
                    else:time.sleep(.5)
                else:raise RequestHumanTakeover('Claim overlay did not return to reward tabs')
            observations.append({'tab':tab,'text':[b.ocr_text for b in self._read()]})
        return observations
