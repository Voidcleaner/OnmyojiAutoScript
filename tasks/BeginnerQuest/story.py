"""Reusable bounded story dispatch with novice-task verification."""
import json
from pathlib import Path
from module.exception import TaskEnd, RequestHumanTakeover
from tasks.BeginnerQuest.novice_hub import NoviceHub
from tasks.BeginnerQuest.script_task import ScriptTask


class StoryRunner:
    def __init__(self, config, device):
        self.config,self.device=config,device

    def run_chapter(self, chapter=None):
        hub=NoviceHub(self.config,self.device)
        state_path=Path('log/beginner_quest')/self.config.config_name/'state.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {}
        resuming=state.get('battle_pending') or state.get('prepare_clicked')
        before_level,before=(None,None) if resuming else hub.scan()
        if chapter is not None and not resuming:
            if not any(o.kind=='story' and o.target==chapter for o in before.objectives):
                raise RequestHumanTakeover('Story requirement not verified in novice tasks')
            hub.open_story_objective(chapter)
        # No target means use recognized courtyard NPCs only. The visual runner
        # enforces time/action limits, stops on loss and saves unknown screens.
        runner=ScriptTask(self.config,self.device)
        try:
            runner.run()
        except TaskEnd:
            pass
        if runner.battle_pending or runner.prepare_clicked:
            return {'status':'resume_battle','chapter':chapter,
                    'player_level_before':before_level,'player_level_after':None}
        after_level,after=hub.scan()
        completed=chapter is not None and not any(
            o.kind=='story' and o.target==chapter for o in after.objectives)
        return {'status':'objective_cleared' if completed else 'replan_needed',
                'chapter':chapter,'player_level_before':before_level,
                'player_level_after':after_level,'stage':after.stage,
                'progress':after.progress}
