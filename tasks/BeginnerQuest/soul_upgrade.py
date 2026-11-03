"""Commit one bounded novice soul upgrade after a verified material preview."""
import re
import time
import cv2
from pathlib import Path
from module.exception import RequestHumanTakeover
from module.ocr.models import get_ocr_model
from tasks.BeginnerQuest.novice_hub import NoviceHub
from tasks.BeginnerQuest.vision import choose_text
from tasks.GameUi.page import page_main


def preview_cost(boxes):
    values=[int(b.ocr_text) for b in boxes if b.score>=.8 and re.fullmatch(r'\d+',b.ocr_text)
            and 780<b.box[:,0].mean()<900 and 610<b.box[:,1].mean()<675]
    return values[0] if len(values)==1 else None


class SoulUpgradeAdapter(NoviceHub):
    def _number(self,roi):
        x1,y1,x2,y2=roi
        image=cv2.resize(self.device.image[y1:y2,x1:x2],None,fx=4,fy=4)
        values=[int(b.ocr_text) for b in get_ocr_model().detect_and_ocr(image)
                if b.score>=.7 and re.fullmatch(r'\d+',b.ocr_text)]
        if len(values)==1:return values[0]
        if roi==(990,345,1045,385):
            template=cv2.imread(str(Path(__file__).parent/'templates'/'soul_level_7.png'))
            template=cv2.cvtColor(template,cv2.COLOR_BGR2RGB)
            crop=self.device.image[y1:y2,x1:x2]
            if cv2.minMaxLoc(cv2.matchTemplate(crop,template,cv2.TM_CCOEFF_NORMED))[1]>=.97:return 7
        return None

    def finish_preview(self,target=3,max_coin=14000):
        """Requires an inspected one- or two-material four-star Qingjigui preview.

        This never auto-selects arbitrary souls or adds more materials. A caller
        must first verify the dedicated material card; the full menu adapter is
        intentionally separate from this one-shot spending gate.
        """
        if target not in (3,7):raise ValueError('Only calibrated novice level-3/7 previews are supported')
        boxes=self._read()
        title=choose_text(boxes,('御魂强化',),(70,0,350,90),'title')
        cost=preview_cost(boxes)
        expected_xp='8750/1500' if target==3 else '19500/3750'
        xp=choose_text(boxes,(expected_xp,),(760,375,1050,420),'material_preview')
        if target==7 and self._number((880,345,945,385))!=3:
            raise RequestHumanTakeover('Level-7 preview requires current level 3')
        level=self._number((990,345,1045,385))
        if not title or not xp or level!=target or cost is None or not 0<cost<=max_coin:
            raise RequestHumanTakeover(f'Soul preview not verified: level={level}, cost={cost}')
        fire=choose_text(boxes,('强化',),(930,590,1130,690),'NOVICE_SOUL_UPGRADE')
        if not fire:raise RequestHumanTakeover('Soul upgrade button not verified')
        self._tap(fire.point)
        self.wait_result(target,allow_material_confirmation=True)
        self.goto_page(page_main)
        return {'level':target,'coin':cost,'material':'four-star Qingjigui','quantity':1 if target==3 else 2}

    def wait_result(self,target=3,allow_material_confirmation=False):
        confirmed=False
        for _ in range(20):
            boxes=self._read()
            text=''.join(b.ocr_text for b in boxes)
            if choose_text(boxes,('御魂强化',),(70,0,350,90),'title'):
                result=choose_text(boxes,(f'Lv.{target}',),(970,220,1080,290),'verified_result')
                previous=choose_text(boxes,('Lv.0','Lv.3'),(790,220,925,290),'previous_level')
                close=choose_text(boxes,('确定',),(780,570,960,660),'result_confirm')
                if result and previous and close:
                    self._tap(close.point)
                    return True
            if allow_material_confirmation and not confirmed and '高级材料' in text and '强化' in text:
                confirm=choose_text(boxes,('确定',),(550,350,950,550),'CONFIRM_VERIFIED_SOUL_MATERIAL')
                if confirm:
                    self._tap(confirm.point)
                    confirmed=True
                    continue
            if self._number((880,345,945,385))==target:
                return True
            time.sleep(.5)
        raise RequestHumanTakeover('Soul upgrade sent once; inspect result before any retry')
