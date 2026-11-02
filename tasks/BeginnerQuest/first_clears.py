"""Follow novice chapter first-clear routes and require an observed boss victory."""
import json
from pathlib import Path
from module.exception import RequestHumanTakeover
from tasks.BeginnerQuest.leveling import LevelingRunner,read_stamina
from tasks.BeginnerQuest.planner import ModulePlan,read_player_level,run_existing
from tasks.GameUi.page import page_main


class FirstClearRunner(LevelingRunner):
    def run_route(self,chapters,target=40,min_stamina=60,stop_at_milestone=30):
        root=Path('log/beginner_quest')/self.config.config_name
        root.mkdir(parents=True,exist_ok=True);ledger_file=root/'first_clears.json'
        ledger=json.loads(ledger_file.read_text()) if ledger_file.exists() else {}
        for difficulty,chapter in chapters:
            if difficulty not in ('normal','hard') or not 1<=chapter<=28:raise ValueError('Invalid exploration route')
            key=f'{difficulty}:{chapter}'
            if ledger.get(key,{}).get('boss_wins',0)>0:continue
            self.goto_page(page_main);self.screenshot()
            before=read_player_level(self.device.image);stamina=read_stamina(self.device.image)
            if before is None or stamina is None:raise RequestHumanTakeover('First-clear level/stamina not verified')
            if before>=target:return {'status':'complete','player_level':before}
            if stamina<min_stamina:return {'status':'low_stamina','player_level':before,'stamina':stamina}
            module='ExplorationHardAdapter' if difficulty=='hard' else 'Exploration'
            result=run_existing(ModulePlan(module,chapter),self.config,self.device)
            if not isinstance(result,dict) or result.get('boss_wins',0)<1:
                raise RequestHumanTakeover('Exploration ended without verified boss victory; do not record a clear or repeat blindly')
            after=read_player_level(self.device.screenshot())
            ledger[key]={**result,'player_level_before':before,'player_level_after':after}
            ledger_file.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
            print('FIRST_CLEAR',key,json.dumps(ledger[key]),flush=True)
            if after is not None and after>=target:return {'status':'complete','player_level':after}
            if stop_at_milestone and before<stop_at_milestone<=after:
                return {'status':'milestone_replan','player_level':after}
        return {'status':'route_finished','clears':ledger}
