import unittest
from tasks.BeginnerQuest.planner import Snapshot,parse_objective,choose_plan
from tasks.Component.GeneralRoom.teammate_gate import TeammateGate


class PlannerTests(unittest.TestCase):
    def test_layer_is_not_boss_name_number(self):
        goal=parse_objective('通关八岐大蛇御魂副本【御魂·叁层】')
        self.assertEqual((goal.kind,goal.target),('orochi',3))
        self.assertEqual(parse_objective('通关任意觉醒副本【觉醒·叁层】').target,3)

    def test_formation_and_chapter_goals(self):
        self.assertEqual(parse_objective('提升1个式神达成15级').target,15)
        goal=parse_objective('完成【主线探索·困难】第五章')
        self.assertEqual((goal.kind,goal.target),('exploration_hard',5))

    def test_hard_objective_never_dispatches_normal_exploration(self):
        goal=parse_objective('完成【主线探索·困难】第五章')
        self.assertEqual(choose_plan(Snapshot(28,requirements=[goal],unlocked_chapter=9)).module,'ExplorationHardAdapter')

    def test_rewards_before_consuming_stamina(self):
        self.assertEqual(choose_plan(Snapshot(12,unclaimed_rewards=True)).module,'ClaimNoviceRewards')

    def test_party_requires_user_level_and_actual_availability(self):
        self.assertNotEqual(choose_plan(Snapshot(14,experience_available=True)).module,'ExperienceYoukai')
        self.assertNotEqual(choose_plan(Snapshot(15)).module,'ExperienceYoukai')
        self.assertTrue(choose_plan(Snapshot(15,experience_available=True)).requires_teammate)

    def test_failed_build_is_not_retried_until_changed(self):
        goal=parse_objective('通关八岐大蛇御魂副本【御魂·叁层】')
        state=Snapshot(12,requirements=[goal],failures={goal.key:'initial'})
        self.assertNotEqual(choose_plan(state).module,'Orochi')
        state.build_revision='upgraded'
        self.assertEqual(choose_plan(state).module,'Orochi')

    def test_no_jump_to_locked_chapters(self):
        goal=parse_objective('完成【主线探索·困难】第五章')
        state=Snapshot(12,requirements=[goal],unlocked_chapter=3,cleared_chapter=2)
        self.assertEqual(choose_plan(state).target,3)

    def test_no_teammate_defer_allows_other_progress(self):
        state=Snapshot(15,experience_available=True,deferred_modules={'ExperienceYoukai'})
        self.assertNotEqual(choose_plan(state).module,'ExperienceYoukai')

    def test_novice_rows_use_go_buttons_and_exclude_completed_or_paid_rows(self):
        import numpy as np
        from types import SimpleNamespace
        from tasks.BeginnerQuest.novice_hub import observe_tasks
        def b(text,x,y):
            return SimpleNamespace(ocr_text=text,score=.99,box=np.array([[x-5,y-5],[x+5,y-5],[x+5,y+5],[x-5,y+5]]))
        rows=[b('阶段·三',350,298),b('5/9',350,372),b('12/60',275,156),b('完成【主线探索·困难】第五章',700,268),b('前往',1112,268),b('将1个御魂提升至3级',700,362),b('前往',1112,362),b('99解锁',1120,120),b('通关御魂·伍层',700,550),b('已完成',1112,550)]
        result=observe_tasks(rows)
        self.assertEqual((result.stage,result.progress,result.handbook_level),(3,(5,9),12))
        self.assertEqual([(g.kind,g.target) for g in result.objectives],[('exploration_hard',5),('soul_upgrade',3)])

    def test_explicit_story_precedes_repeat_farming(self):
        goal=parse_objective('完成第十一章剧情')
        self.assertEqual((goal.kind,goal.target),('story',11))
        plan=choose_plan(Snapshot(30,requirements=[goal],experience_available=True))
        self.assertEqual((plan.module,plan.target),('BeginnerQuest',11))
        state=Snapshot(30,requirements=[goal],failures={goal.key:'initial'})
        self.assertNotEqual(choose_plan(state).module,'BeginnerQuest')

    def test_party_countdown_is_scoped_to_requested_row(self):
        import numpy as np
        from types import SimpleNamespace
        from tasks.Component.GeneralRoom.cooldown import row_cooldown,parse_countdown
        def b(text,x,y):
            return SimpleNamespace(ocr_text=text,score=.99,box=np.array([[x,y],[x,y],[x,y],[x,y]]))
        boxes=[b('经验妖怪',254,205),b('8时13分',186,180),b('石距',254,424),b('00:51',186,399)]
        self.assertEqual(row_cooldown(boxes,'经验妖怪'),29580)
        self.assertEqual(row_cooldown(boxes,'石距'),51)
        self.assertIsNone(row_cooldown(boxes,'金币妖怪'))
        self.assertIsNone(parse_countdown('437+'))
        self.assertEqual(parse_countdown('1小时2分钟3秒'),3723)

    def test_novice_exploration_keeps_disabled_candidate_rotation(self):
        from types import SimpleNamespace
        from tasks.BeginnerQuest.exploration_hard import ExplorationNormalAdapter
        from tasks.Exploration.config import AutoRotate
        adapter=object.__new__(ExplorationNormalAdapter)
        adapter.config=SimpleNamespace(exploration=SimpleNamespace(exploration_config=SimpleNamespace(auto_rotate=AutoRotate.no)))
        self.assertFalse(adapter.ui_click(adapter.I_E_AUTO_ROTATE_OFF))

    def test_exploration_fire_waits_for_positive_battle_entry(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        from tasks.BeginnerQuest.exploration_hard import ExplorationNormalAdapter
        from tasks.Exploration.base import Scene
        task=object.__new__(ExplorationNormalAdapter)
        task.device=Mock(image=None);task.screenshot=Mock();task.appear=Mock(return_value=True)
        task.get_current_scene=Mock(side_effect=[Scene.MAIN,Scene.BATTLE_PREPARE])
        task.run_general_battle=Mock(return_value=True);task.minions_cnt=0
        task._config=SimpleNamespace(general_battle_config=None)
        button=Mock();button.coord.return_value=(646,99)
        with patch('tasks.BeginnerQuest.exploration_hard.get_ocr_model') as ocr,patch('tasks.BeginnerQuest.exploration_hard.time.sleep'):
            ocr.return_value.detect_and_ocr.return_value=[]
            self.assertTrue(task.fire(button))
        task.device.click.assert_called_once_with(646,130,control_check=False,control_name='NOVICE_START_BATTLE')
        self.assertEqual(task.minions_cnt,1)
        task.run_general_battle.assert_called_once()
        from module.exception import RequestHumanTakeover
        task.get_current_scene=Mock(return_value=Scene.MAIN)
        task.run_general_battle.reset_mock();task.minions_cnt=0
        with patch('tasks.BeginnerQuest.exploration_hard.get_ocr_model') as ocr,patch('tasks.BeginnerQuest.exploration_hard.time.sleep'),patch('tasks.BeginnerQuest.exploration_hard.time.monotonic',side_effect=[0,0,21]):
            ocr.return_value.detect_and_ocr.return_value=[]
            with self.assertRaises(RequestHumanTakeover):task.fire(button)
        task.run_general_battle.assert_not_called()
        self.assertEqual(task.minions_cnt,0)

    def test_fast_exploration_settlement_is_not_mistaken_for_missing_entry(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        from tasks.BeginnerQuest.exploration_hard import ExplorationNormalAdapter
        from tasks.Exploration.base import Scene
        task=object.__new__(ExplorationNormalAdapter)
        task.device=Mock(image=None);task.screenshot=Mock()
        task.get_current_scene=Mock(return_value=Scene.UNKNOWN)
        task.appear=Mock(side_effect=lambda rule,**kw:rule is task.I_REWARD_GOLD)
        task.run_general_battle=Mock();task.battle_wait=Mock(return_value=True)
        task.minions_cnt=0;task.current_count=0
        with patch('tasks.BeginnerQuest.exploration_hard.get_ocr_model') as ocr:
            ocr.return_value.detect_and_ocr.return_value=[]
            self.assertTrue(task.fire(Mock()))
        task.run_general_battle.assert_not_called()
        task.battle_wait.assert_called_once_with(random_click_swipt_enable=False)
        task.device.click.assert_not_called()
        self.assertEqual((task.current_count,task.minions_cnt),(1,1))

    def test_stop_at_40(self):
        self.assertEqual(choose_plan(Snapshot(40,experience_available=True)).module,'Complete')

    def test_teammate_must_remain_present_for_delay(self):
        gate=TeammateGate(delay=4)
        self.assertFalse(gate.ready(False,0))
        self.assertFalse(gate.ready(True,10))
        self.assertFalse(gate.ready(True,13.9))
        self.assertTrue(gate.ready(True,14))
        self.assertFalse(gate.ready(False,15))
        self.assertFalse(gate.ready(True,16))
        self.assertFalse(gate.ready(True,19.9))
        self.assertTrue(gate.ready(True,20))
