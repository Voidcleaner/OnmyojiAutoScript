"""Select and verify hard difficulty before reusing the existing exploration task."""
import time
import cv2
import numpy as np
from module.exception import RequestHumanTakeover
from module.ocr.models import get_ocr_model
from tasks.Exploration.script_task import ScriptTask as ExplorationTask


class ExplorationHardAdapter(ExplorationTask):
    difficulty="困难"
    def fire(self, button):
        from tasks.Exploration.base import Scene
        from tasks.BeginnerQuest.vision import chat_close_action,exploration_click_point
        deadline=time.monotonic()+10
        clicks=0
        while time.monotonic()<deadline:
            self.screenshot()
            action=chat_close_action(get_ocr_model().detect_and_ocr(self.device.image))
            if action:
                self.device.click(*action.point,control_check=False,control_name=action.name)
                time.sleep(.5)
                continue
            scene=self.get_current_scene()
            if scene in (Scene.BATTLE_PREPARE,Scene.BATTLE_FIGHTING):
                won=self.run_general_battle(self._config.general_battle_config)
                if won:self.minions_cnt+=1
                return bool(won)
            if scene==Scene.MAIN and self.appear(button) and clicks<3:
                point=exploration_click_point(button.coord())
                self.device.click(*point,control_check=False,control_name='NOVICE_START_BATTLE')
                self.device.stuck_record_clear()
                clicks+=1
            time.sleep(.7)
        raise RequestHumanTakeover('Exploration battle entry not confirmed; do not wait on the map indefinitely')

    def _reset_search_state(self, reset_swipe_cnt=False):
        super()._reset_search_state(reset_swipe_cnt)
        search=getattr(self,'_novice_scene_search',None)
        if search is not None:search.reset()

    def _search_next_area(self):
        from tasks.Exploration.config import UpType
        from tasks.BeginnerQuest.search import SceneSearch
        from module.logger import logger
        if self.config.exploration.exploration_config.up_type!=UpType.ALL:
            return super()._search_next_area()
        if not self.search_fail_timer.started():
            self.search_fail_timer.start()
            return
        if not self.search_fail_timer.reached():return
        search=getattr(self,'_novice_scene_search',None)
        if search is None:
            search=self._novice_scene_search=SceneSearch(limit=8)
        drag=search.next_drag(self.device.image)
        if drag is None:
            logger.warning('Novice exploration exhausted bounded search in both directions')
            self._reset_search_state(reset_swipe_cnt=True)
            self.quit_explore()
            return
        logger.info('Novice exploration search %s/8: %s',search.count,drag)
        self.device.click_record_remove('NOVICE_EXPLORE_SEARCH')
        if getattr(self.device,'is_desktop',False):
            self.device.swipe_desktop_window_message(*drag,hold_time=.8)
        else:
            self.device.swipe(*drag,control_name='NOVICE_EXPLORE_SEARCH')
        time.sleep(.3)
        self.screenshot()
        self.search_fail_timer.reset()

    def ui_click(self, click, *args, **kwargs):
        from tasks.Exploration.config import AutoRotate
        if (click is self.I_E_AUTO_ROTATE_OFF
                and self.config.exploration.exploration_config.auto_rotate==AutoRotate.no):
            # The inherited loop enables candidate rotation even when disabled.
            # Novice batches keep their verified party and fire fights directly.
            return False
        return super().ui_click(click,*args,**kwargs)

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
        if len(matches)==1:
            x,y=map(int,matches[0].box.mean(axis=0))
        else:
            # The full-screen detector can merge the small torii/label text.
            # Re-read the left menu at higher resolution before giving up.
            for _ in range(3):
                self.screenshot()
                crop=cv2.resize(self.device.image[200:380,10:180],None,fx=3,fy=3)
                labels=[b for b in get_ocr_model().detect_and_ocr(crop) if b.score>=.7 and self.difficulty in b.ocr_text
                        and not ('普通' in b.ocr_text and '困难' in b.ocr_text)]
                if len(labels)==1:
                    cx,cy=labels[0].box.mean(axis=0)
                    x,y=int(cx/3)+10,int(cy/3)+200
                    break
                time.sleep(.5)
            else:
                raise RequestHumanTakeover('Exploration difficulty selector not verified')
        self.device.click(x,y,control_check=False,control_name='NOVICE_EXPLORATION_'+self.difficulty)
        time.sleep(1)
        self.screenshot()
        patch=self.device.image[y-14:y+15,20:180].astype(np.float32)
        selected=(patch[:,:,0]>patch[:,:,1]*1.5)&(patch[:,:,0]>100)
        if selected.mean()<.25:
            raise RequestHumanTakeover('Hard exploration tab did not become selected')


class ExplorationNormalAdapter(ExplorationHardAdapter):
    difficulty="普通"
