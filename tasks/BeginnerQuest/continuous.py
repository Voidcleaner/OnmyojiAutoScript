"""Bounded, resumable account progression using existing OAS tasks."""
import json
import time
from pathlib import Path
from module.exception import TaskEnd
from tasks.BeginnerQuest.leveling import LevelingRunner
from tasks.BeginnerQuest.planner import read_player_level
from tasks.BeginnerQuest.script_task import ScriptTask
from tasks.GameUi.page import page_main


class ContinuousProgression(LevelingRunner):
    def _record(self, **state):
        path=Path('log/beginner_quest')/self.config.config_name/'continuous.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
        print('CONTINUOUS_PROGRESS',json.dumps(state,ensure_ascii=False),flush=True)
        return state

    def _story_pending(self):
        config=getattr(self,'config',None)
        if config is None:return False
        path=Path('log/beginner_quest')/config.config_name/'state.json'
        if not path.exists():return False
        state=json.loads(path.read_text(encoding='utf-8'))
        return bool(state.get('battle_pending') or state.get('prepare_clicked'))

    def _story_batch(self):
        options=self.config.beginner_quest.quest_options
        previous=(options.max_seconds,options.max_actions,options.max_battles)
        try:
            options.max_seconds=300;options.max_actions=300;options.max_battles=20
            story=ScriptTask(self.config,self.device)
            try:story.run()
            except TaskEnd:pass
            return bool(story.battle_pending or story.prepare_clicked)
        finally:
            options.max_seconds,options.max_actions,options.max_battles=previous

    def run(self,chapter,target=40,min_stamina=200,max_seconds=14400):
        if not 1<=chapter<=28 or not 1<=target<=60 or not 60<=max_seconds<=28800:
            raise ValueError('Invalid continuous progression budget')
        started=time.monotonic();last_story_level=None
        for cycle in range(60):
            if time.monotonic()-started>=max_seconds:
                return self._record(status='time_limit',target=target,cycle=cycle)
            if self._story_pending():
                self._story_batch()
                self._record(status='resume_story_battle',target=target,cycle=cycle)
                continue
            self.goto_page(page_main);self.screenshot()
            level=read_player_level(self.device.image)
            if level is None:
                return self._record(status='unverified_level',target=target,cycle=cycle)
            if level>=target:
                return self._record(status='complete',player_level=level,target=target,cycle=cycle)
            # Run courtyard story once per verified player level. The existing
            # runner handles gates, prepares battles, stops on loss and resumes.
            if level!=last_story_level:
                if self._story_batch():
                    self._record(status='resume_story_battle',player_level=level,target=target,cycle=cycle)
                    continue
                last_story_level=level
            result=self.run_to(chapter,target=min(level+1,target),max_batches=3,
                               min_stamina=min_stamina,xp_only=False,difficulty='hard')
            self._record(status=result['status'],player_level=result['player_level'],
                         target=target,cycle=cycle,leveling=result)
            if result['status'] not in ('complete','batch_limit'):
                return result
        return self._record(status='cycle_limit',target=target)
