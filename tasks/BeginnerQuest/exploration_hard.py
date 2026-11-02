"""Select and verify hard difficulty before reusing the existing exploration task."""
import time
import numpy as np
from module.exception import RequestHumanTakeover
from module.ocr.models import get_ocr_model
from tasks.Exploration.script_task import ScriptTask as ExplorationTask


class ExplorationHardAdapter(ExplorationTask):
    difficulty="困难"
    def run(self):
        from tasks.Exploration.base import Scene
        self.screenshot()
        if self.get_current_scene()==Scene.MAIN:
            self.quit_explore()
        self.pre_process()
        return super().run()

    def pre_process(self):
        super().pre_process()
        # An already open chapter bypasses WORLD in run_solo. Verify the
        # difficulty here as well, before the first exploration can start.
        self.open_expect_level()

    def open_expect_level(self):
        super().open_expect_level()
        self.screenshot()
        boxes=get_ocr_model().detect_and_ocr(self.device.image)
        expected=self.config.exploration.exploration_config.exploration_level
        expected=getattr(expected,'value',expected)
        if not any(b.ocr_text.replace('草','章')==expected and b.box[:,1].mean()<80 and b.box[:,0].mean()<350 for b in boxes):
            raise RequestHumanTakeover('Exploration chapter title does not match requested chapter')
        matches=[b for b in boxes if b.score>=.8 and self.difficulty in b.ocr_text
                 and 15<b.box[:,0].mean()<200 and 180<b.box[:,1].mean()<400]
        if len(matches)!=1:
            raise RequestHumanTakeover('Hard exploration selector not verified')
        x,y=map(int,matches[0].box.mean(axis=0))
        self.device.click(x,y,control_check=False,control_name='NOVICE_EXPLORATION_'+self.difficulty)
        time.sleep(1)
        self.screenshot()
        patch=self.device.image[y-14:y+15,20:180].astype(np.float32)
        selected=(patch[:,:,0]>patch[:,:,1]*1.5)&(patch[:,:,0]>100)
        if selected.mean()<.25:
            raise RequestHumanTakeover('Hard exploration tab did not become selected')


class ExplorationNormalAdapter(ExplorationHardAdapter):
    difficulty="普通"
