# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd, RequestHumanTakeover
from module.base.timer import Timer
from tasks.Component.GeneralRoom.teammate_gate import TeammateGate

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_team, page_shikigami_records
from tasks.Component.continue_prompt import handle_continue_prompt
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul


class ScriptTask(GameUi, GeneralBattle, GeneralRoom, GeneralInvite, SwitchSoul):

    def run(self):
        conf = self.config.tako
        if conf.switch_soul.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(conf.switch_soul.switch_group_team)

        if conf.switch_soul.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(conf.switch_soul.group_name,
                                         conf.switch_soul.team_name)
        # 加成
        conf_buff = conf.tako_config
        if conf_buff.enable:
            self.goto_page(page_main)
            self.open_buff()
            if conf_buff.buff_gold_50_click:
                self.gold_50()
            if conf_buff.buff_gold_100_click:
                self.gold_100()
            if conf_buff.buff_exp_50_click:
                self.exp_50()
            if conf_buff.buff_exp_100_click:
                self.exp_100()
            self.close_buff()

        # 进入
        self.goto_page(page_team)
        if 5 <= self.start_time.weekday() <= 6:
            # 周末
            self.check_zones('喷怒的石距')
        else:
            self.check_zones('石距')
        from tasks.Component.GeneralRoom.cooldown import row_cooldown
        from module.ocr.models import get_ocr_model
        self.screenshot()
        zone='喷怒的石距' if 5<=self.start_time.weekday()<=6 else '石距'
        cooldown=row_cooldown(get_ocr_model().detect_and_ocr(self.device.image),zone)
        if cooldown:
            self.progression_outcome={'status':'cooldown','retry_after_seconds':cooldown}
            self.exit_task()
        if not self.create_room():
            self.progression_outcome = 'unavailable'
            self.exit_task()
        self.ensure_public()
        self.create_ensure()
        # 进入到了房间里面
        wait_timer = Timer(60)
        wait_timer.start()
        teammate_gate = TeammateGate()
        while 1:
            self.screenshot()

            if not self.is_in_room():
                continue
            present = not self.appear(self.I_ADD_1)
            if not present and wait_timer.reached():
                self.progression_outcome = 'no_teammate'
                logger.warning('Wait for too long, exit')
                self.exit_room()
                break
            if teammate_gate.ready(present):
                self.screenshot()
                if not self.is_in_room() or self.appear(self.I_ADD_1):
                    teammate_gate.ready(False)
                    continue
                logger.info('Teammate remained for 3-5 seconds; start as host')
                self.click_fire()
                self.run_general_battle()
                break
        self.exit_task()

    def exit_task(self):
        """
        退出任务
        :return:
        """
        conf_buff = self.config.tako.tako_config
        self.goto_page(page_main)
        if conf_buff.enable:
            self.goto_page(page_main)
            self.open_buff()
            if conf_buff.buff_gold_50_click:
                self.gold_50(False)
            if conf_buff.buff_gold_100_click:
                self.gold_100(False)
            if conf_buff.buff_exp_50_click:
                self.exp_50(False)
            if conf_buff.buff_exp_100_click:
                self.exp_100(False)
            self.close_buff()

        self.set_next_run(task='Tako', success=True, finish=False)
        raise TaskEnd('Tako')

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        while 1:
            self.screenshot()
            if self.appear(self.I_WIN) or self.appear(self.I_REWARD):
                logger.info('Win battle')
                self.ui_click_until_disappear(self.I_WIN)
                settlement_timer=Timer(25).start()
                while not settlement_timer.reached():
                    self.screenshot()
                    if handle_continue_prompt(self):
                        continue
                    if self.match_page_once(page_main) or self.match_page_once(page_team):
                        return True
                    if self.appear(self.I_REWARD) or self.appear(self.I_REWARD_GOLD):
                        self.click(self.C_REWARD_2, interval=2)
                        continue
                    if self.close_unknown_pages():
                        continue
                raise RequestHumanTakeover('Tako won but settlement page did not close; inspect instead of repeated blind clicks')
                return True

            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()



