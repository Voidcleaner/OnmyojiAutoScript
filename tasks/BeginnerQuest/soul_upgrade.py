"""Commit one bounded novice soul upgrade after a verified material preview."""
import re
import time
import cv2
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
        return values[0] if len(values)==1 else None

    def finish_preview(self,target=3,max_coin=14000):
        """Requires the already inspected single four-star Qingjigui preview.

        This never auto-selects arbitrary souls or adds more materials. A caller
        must first verify the dedicated material card; the full menu adapter is
        intentionally separate from this one-shot spending gate.
        """
        if target!=3:raise ValueError('Only novice level-3 soul upgrade is calibrated')
        boxes=self._read()
        title=choose_text(boxes,('御魂强化',),(70,0,350,90),'title')
        cost=preview_cost(boxes)
        xp=choose_text(boxes,('8750/1500',),(760,375,1050,420),'material_preview')
        level=self._number((990,345,1045,385))
        if not title or not xp or level!=target or cost is None or not 0<cost<=max_coin:
            raise RequestHumanTakeover(f'Soul preview not verified: level={level}, cost={cost}')
        fire=choose_text(boxes,('强化',),(930,590,1130,690),'NOVICE_SOUL_UPGRADE')
        if not fire:raise RequestHumanTakeover('Soul upgrade button not verified')
        self._tap(fire.point)
        self.wait_result(target,allow_material_confirmation=True)
        self.goto_page(page_main)
        return {'level':target,'coin':cost,'material':'four-star Qingjigui','quantity':1}

    def wait_result(self,target=3,allow_material_confirmation=False):
        confirmed=False
        for _ in range(20):
            boxes=self._read()
            text=''.join(b.ocr_text for b in boxes)
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
