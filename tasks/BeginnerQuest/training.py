"""One-shot feeding gate; menu navigation and material selection remain separate."""
import re
import time
from pathlib import Path
from module.exception import RequestHumanTakeover
from tasks.BeginnerQuest.soul_upgrade import SoulUpgradeAdapter
from tasks.BeginnerQuest.vision import template_action,choose_text


def training_preview(boxes):
    levels={}
    coins=[]
    for b in boxes:
        if b.score<.75:continue
        x,y=b.box.mean(axis=0)
        m=re.fullmatch(r'LV[.。]?\s*(\d+)\s*/\s*(\d+)',b.ocr_text.upper())
        if m and 520<y<580:
            if 650<x<780:levels['before']=tuple(map(int,m.groups()))
            if 850<x<1020:levels['after']=tuple(map(int,m.groups()))
        if 700<x<810 and 625<y<680 and b.ocr_text.isdigit():coins.append(int(b.ocr_text))
    return levels,coins[0] if len(coins)==1 else None


def training_result(boxes):
    values=[]
    for b in sorted(boxes,key=lambda b:float(b.box[:,0].mean())):
        x,y=b.box.mean(axis=0)
        if b.score>=.75 and 650<x<1080 and 200<y<320:
            values.extend(int(n) for n in re.findall(r'LV[.。]?\s*(\d+)',b.ocr_text.upper()))
    return tuple(values) if len(values)==2 else None


class TrainingAdapter(SoulUpgradeAdapter):
    SLOT_CENTERS=((590,185),(590,305),(590,425),(590,548),(1050,185),(1050,305),(1050,425),(1050,548))

    def commit_preview(self,before,after,materials,max_coin):
        boxes=self._read()
        levels,coin=training_preview(boxes)
        title=choose_text(boxes,('式神升级',),(70,0,350,90),'title')
        if not title or levels.get('before')!=before or levels.get('after')!=after or coin is None or not 0<coin<=max_coin:
            raise RequestHumanTakeover(f'Training preview not verified: levels={levels}, coin={coin}')
        if len(materials)>8:raise ValueError('Too many materials')
        root=Path(__file__).parent/'templates'
        for index,(x,y) in enumerate(self.SLOT_CENTERS):
            if index<len(materials):
                kind,level=materials[index]
                if kind not in ('red','blue','n_tubikabe'):raise ValueError('Only experience daruma or verified level-1 N Tubi may be fed')
                if kind=='n_tubikabe' and level!=1:raise ValueError('Only level-1 N fodder is calibrated')
                image=root/f'food_{kind}.png'
                actual=self._number((x-48,y-50,x-12,y-18))
                if actual!=level and level in (1,13):
                    candidates=[root/f'food_level_{level}.png']
                    if level==1:candidates.append(root/'food_level_1_large.png')
                    if kind=='n_tubikabe':candidates.append(root/'food_n_tubikabe_level_1.png')
                    if kind=='blue':candidates.append(root/f'food_blue_level_{level}.png')
                    if any(template_action(self.device.image,p,'food_level',region=(x-50,y-55,x-5,y-15),threshold=.9 if kind=='blue' else .95) for p in candidates):actual=level
                if actual!=level or not template_action(self.device.image,image,'food',region=(x-46,y-45,x+46,y+45),threshold=.9):
                    raise RequestHumanTakeover(f'Training material {index+1} identity/level not verified: {actual}')
            elif not template_action(self.device.image,root/'food_plus.png','empty',region=(x-28,y-28,x+28,y+28),threshold=.9):
                raise RequestHumanTakeover('Unexpected selected material; do not consume it')
        confirm=choose_text(boxes,('确认',),(810,610,970,690),'training_confirm')
        if not confirm:raise RequestHumanTakeover('Training confirmation missing')
        self._tap(confirm.point)
        for _ in range(15):
            boxes=self._read()
            if self.finish_result(before[0],after[0],boxes):
                return {'level':after[0],'coin':coin,'materials':materials}
            levels,_=training_preview(boxes)
            if levels.get('before')==after:
                done=choose_text(boxes,('确定',),(800,550,1100,670),'close_training_result')
                if done:self._tap(done.point)
                return {'level':after[0],'coin':coin,'materials':materials}
            time.sleep(.5)
        raise RequestHumanTakeover('Training submitted once; inspect result before retry')


    def finish_result(self,before,after,boxes=None):
        if boxes is None:boxes=self._read()
        if training_result(boxes)!=(before,after):return False
        done=choose_text(boxes,('确定',),(750,550,1100,670),'close_training_result')
        if not done:return False
        self._tap(done.point)
        return True
