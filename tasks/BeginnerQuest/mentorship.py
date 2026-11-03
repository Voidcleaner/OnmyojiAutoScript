"""Coordinate an existing mentor/apprentice pair; never start a solo guardian run."""
import json
import cv2
import re
import time
from pathlib import Path
from module.exception import RequestHumanTakeover
from tasks.BeginnerQuest.novice_hub import NoviceHub
from tasks.BeginnerQuest.vision import choose_text
from tasks.Component.idle_courtyard import handle_idle_courtyard
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralInvite.assets import GeneralInviteAssets
from tasks.Component.GeneralRoom.teammate_gate import TeammateGate


def guardian_remaining(boxes):
    for b in boxes:
        if b.score<.7:continue
        text=b.ocr_text.replace(' ','')
        match=re.search(r'剩余挑战次数[：:]?(\d+)/5',text)
        if match and 0<=int(match[1])<=5:return int(match[1])
    return None


def paired_guardian_room(boxes,teacher_name,pupil_name):
    text=''.join(b.ocr_text.replace(' ','') for b in boxes if b.score>=.7)
    return ('协战队伍' in text and '目标守护历练' in text and teacher_name in text and pupil_name in text
            and '邀请后辈' not in text)


class GuardianPlayer(NoviceHub,GeneralBattle):
    def on_battle_failed(self):
        raise RequestHumanTakeover('Guardian battle lost; improve mentor formation before retry')


class MentorshipRunner:
    def __init__(self,teacher_config,teacher_device,pupil_config,pupil_device,teacher_name,pupil_name):
        if teacher_config.config_name==pupil_config.config_name or not teacher_name or not pupil_name or teacher_name==pupil_name:
            raise ValueError('Two independent existing mentor/apprentice identities required')
        self.teacher=GuardianPlayer(teacher_config,teacher_device)
        self.pupil=GuardianPlayer(pupil_config,pupil_device)
        self.teacher_name,self.pupil_name=teacher_name,pupil_name
        self._invitation_sent=False
        self.root=Path('log/beginner_quest')/pupil_config.config_name
        self.root.mkdir(parents=True,exist_ok=True)

    def _save(self,status,**details):
        state={'status':status,**details}
        (self.root/'mentorship.json').write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
        print('MENTORSHIP',json.dumps(state,ensure_ascii=False),flush=True)
        return state

    def _wake(self,player):
        player.screenshot()
        if handle_idle_courtyard(player):time.sleep(1)
        player._clear_completion()

    def _open_room(self):
        h=self.teacher;boxes=h._read()
        text=''.join(b.ocr_text.replace(' ','') for b in boxes)
        if '是否邀请队友继续进行战斗' in text:
            confirm=choose_text(boxes,('确定',),(650,350,950,520),'CONTINUE_VERIFIED_PAIR')
            if not confirm:raise RequestHumanTakeover('Continue-pair confirmation not verified')
            h.device.click(*confirm.point,control_check=False,control_name=confirm.name)
            self._invitation_sent=True
            return None
        if any('协战队伍' in b.ocr_text for b in boxes) and any('守护历练' in b.ocr_text for b in boxes):return None
        if not all(any(name in b.ocr_text for b in boxes) for name in (self.teacher_name,self.pupil_name)):
            raise RequestHumanTakeover('Open the verified mentor pair page before guardian runs')
        tab=choose_text(boxes,('协同',),(700,0,900,90),'GUARDIAN_COOP_TAB')
        if not tab:raise RequestHumanTakeover('Mentor cooperation tab not verified')
        boxes=h._tap(tab.point);remaining=guardian_remaining(boxes)
        if remaining is None:raise RequestHumanTakeover('Daily guardian allowance not verified')
        if remaining==0:return 0
        action=choose_text(boxes,('前往',),(1100,530,1270,640),'GUARDIAN_ROOM')
        if not action:raise RequestHumanTakeover('Guardian room entrance not verified')
        h._tap(action.point)
        return remaining

    def _join_pair(self):
        th,ph=self.teacher,self.pupil
        self._wake(ph)
        if not self._invitation_sent:
            boxes=th._read()
            if paired_guardian_room(boxes,self.teacher_name,self.pupil_name):return
            invite=choose_text(boxes,('邀请后辈',),(600,250,1100,450),'INVITE_VERIFIED_APPRENTICE')
            if invite:
                boxes=th._tap(invite.point)
            if any('在线前辈/后辈' in b.ocr_text for b in boxes):
                row=choose_text(boxes,(self.pupil_name,),(350,150,950,450),'SELECT_VERIFIED_APPRENTICE')
                if not row:raise RequestHumanTakeover('Expected apprentice missing from guardian invitation list')
                boxes=th._tap(row.point)
                confirm=choose_text(boxes,('邀请',),(650,500,900,630),'SEND_GUARDIAN_INVITATION')
                if not confirm:raise RequestHumanTakeover('Guardian invitation confirmation not verified')
                th.device.click(*confirm.point,control_check=False,control_name=confirm.name)
            elif not invite:
                raise RequestHumanTakeover('Expected guardian apprentice invitation not verified')
        deadline=time.monotonic()+45
        accepted=False
        while time.monotonic()<deadline:
            pboxes=ph._read()
            text=''.join(b.ocr_text for b in pboxes)
            if (self.teacher_name in text or '前辈邀请你加入' in text) and '守护历练' in text:
                action=choose_text(pboxes,('接受','同意'),(0,100,1280,650),'ACCEPT_VERIFIED_MENTOR')
                if action:
                    ph._tap(action.point);accepted=True
                elif ph.appear(GeneralInviteAssets.I_I_ACCEPT):
                    ph.device.click(*map(int,GeneralInviteAssets.I_I_ACCEPT.front_center()),control_check=False,control_name='ACCEPT_GUARDIAN');accepted=True
                    cv2.imwrite(str(self.root/'guardian_accept_before.png'),cv2.cvtColor(ph.device.image,cv2.COLOR_RGB2BGR))
            if accepted:
                tboxes=th._read()
                if paired_guardian_room(tboxes,self.teacher_name,self.pupil_name):
                    self._invitation_sent=False
                    return
            time.sleep(.3)
        raise RequestHumanTakeover('Apprentice did not join verified guardian room; do not start solo')

    def _wait_joined(self):
        gate=TeammateGate();deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            boxes=self.teacher._read()
            if gate.ready(paired_guardian_room(boxes,self.teacher_name,self.pupil_name)):
                # Fresh positive membership proof immediately before challenge.
                if paired_guardian_room(self.teacher._read(),self.teacher_name,self.pupil_name):return
            time.sleep(.5)
        raise RequestHumanTakeover('Pair membership was not stable for 3–5 seconds')

    def _settle_pupil(self):
        h=self.pupil
        for _ in range(30):
            h.screenshot()
            if any(h.appear(a,threshold=.85) for a in (h.I_WIN,h.I_REWARD,h.I_REWARD_GOLD)):
                if not h.battle_wait(random_click_swipt_enable=False):h.on_battle_failed()
                return
            boxes=h._read()
            if paired_guardian_room(boxes,self.teacher_name,self.pupil_name):return
            if any('获得奖励' in b.ocr_text for b in boxes):h._tap((1100,600))
            time.sleep(.5)
        raise RequestHumanTakeover('Pupil settlement not verified; inspect before another run')

    def _conclude(self,wins,initial_remaining):
        th=self.teacher;boxes=th._read()
        text=''.join(b.ocr_text.replace(' ','') for b in boxes)
        if '是否邀请队友继续进行战斗' in text:
            cancel=choose_text(boxes,('取消',),(350,350,650,520),'END_GUARDIAN_BATCH')
            if not cancel:raise RequestHumanTakeover('End-of-batch confirmation not verified')
            boxes=th._tap(cancel.point)
        for _ in range(10):
            if any(b.ocr_text=='协同' for b in boxes):break
            time.sleep(.5);boxes=th._read()
        remaining=None
        if any(b.ocr_text=='协同' for b in boxes):
            boxes=th._tap((806,45));remaining=guardian_remaining(boxes)
        from tasks.GameUi.default_pages import modern_courtyard
        from tasks.BeginnerQuest.planner import read_player_level
        self.pupil.screenshot()
        level=read_player_level(self.pupil.device.image) if modern_courtyard(self.pupil) else None
        return self._save('daily_complete' if remaining==0 else 'batch_complete',
                          wins=wins,initial_remaining=initial_remaining,
                          verified_remaining=remaining,pupil_level=level)

    def run_guardian(self,max_runs=5):
        if not 1<=max_runs<=5:raise ValueError('Guardian run budget must be 1..5')
        wins=0
        try:
            self._wake(self.pupil)
            remaining=self._open_room()
            if remaining==0:return self._save('daily_complete',wins=0,remaining=0)
            limit=min(max_runs,remaining) if remaining is not None else max_runs
            for index in range(limit):
                if index:self._open_room()
                self._join_pair();self._wait_joined()
                th=self.teacher;boxes=th._read()
                if not paired_guardian_room(boxes,self.teacher_name,self.pupil_name):
                    raise RequestHumanTakeover('Apprentice left before challenge')
                challenge=choose_text(boxes,('挑战','挑'),(1120,550,1280,690),'GUARDIAN_CHALLENGE')
                if challenge:
                    th._tap(challenge.point)
                elif th.appear(GeneralInviteAssets.I_FIRE):
                    th.click(GeneralInviteAssets.I_FIRE,interval=1)
                else:raise RequestHumanTakeover('Guardian challenge button not verified')
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    th.screenshot()
                    if th.is_in_prepare(False) or th.is_in_real_battle(False):break
                    time.sleep(.5)
                else:raise RequestHumanTakeover('Guardian battle entry not verified')
                if not th.run_general_battle(GeneralBattleConfig()):th.on_battle_failed()
                self._settle_pupil();wins+=1
                self._save('won',wins=wins,initial_remaining=remaining)
            return self._conclude(wins,remaining)
        except Exception as exc:
            for label,player in [('teacher',self.teacher),('pupil',self.pupil)]:
                image=getattr(player.device,'image',None)
                if image is not None:
                    cv2.imwrite(str(self.root/f'mentorship_{label}_stopped.png'),cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
            self._save('stopped',wins=wins,reason=f'{type(exc).__name__}: {exc}')
            raise
