import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
from module.exception import RequestHumanTakeover
from tasks.BeginnerQuest.soul_upgrade import preview_cost,SoulUpgradeAdapter
from tasks.Component.optional_prompt import handle_cosmetic_activation,handle_guild_join_prompt


def box(text,x,y):
    return SimpleNamespace(ocr_text=text,score=.99,box=np.array([[x-5,y-5],[x+5,y-5],[x+5,y+5],[x-5,y+5]]))


class NoviceResourceTests(unittest.TestCase):
    def test_cost_only_uses_spending_label_region(self):
        self.assertEqual(preview_cost([box('14000',830,644),box('1330000',1160,47)]),14000)
        self.assertIsNone(preview_cost([box('14000',830,644),box('28000',850,644)]))

    def test_unverified_cost_never_spends(self):
        t=object.__new__(SoulUpgradeAdapter)
        t._read=Mock(return_value=[box('御魂强化',196,43),box('8750/1500',900,396),box('28000',830,644)])
        t._number=Mock(return_value=3);t._tap=Mock()
        with self.assertRaises(RequestHumanTakeover):t.finish_preview()
        t._tap.assert_not_called()

    def test_cosmetic_activation_only_cancels_explicit_prompt(self):
        task=SimpleNamespace(device=Mock())
        self.assertFalse(handle_cosmetic_activation(task,[box('是否购买',640,300),box('取消',525,438)]))
        self.assertTrue(handle_cosmetic_activation(task,[box('是否立即启用“外观”',640,300),box('取消',525,438),box('确定',750,438)]))
        self.assertEqual(task.device.click.call_args.args,(525,438))

    def test_guild_prompt_prevents_reopening_membership_route(self):
        task=SimpleNamespace(device=Mock(),navigator=SimpleNamespace(edge_penalties={}))
        with patch('module.ocr.models.get_ocr_model') as ocr:
            ocr.return_value.detect_and_ocr.return_value=[box('暂未加入任何阴阳寮，是否前往申请加入？',640,300),box('取消',525,438)]
            self.assertTrue(handle_guild_join_prompt(task))
        self.assertEqual(task.navigator.edge_penalties['page_exploration->page_realm_raid'],100)
        task.device.click_record_clear.assert_called_once()

    def test_failed_layer_is_recorded_before_any_cleanup_click(self):
        import json,tempfile
        from pathlib import Path
        from tasks.BeginnerQuest.awakening import AwakeningAdapter
        from tasks.Component.GeneralBattle.general_battle import GeneralBattle
        with tempfile.TemporaryDirectory() as directory:
            task=SimpleNamespace(failed_layers={},current_layer=6,objective_kind='orochi',build_revision='initial',failure_file=Path(directory)/'failure.json')
            with self.assertRaises(RequestHumanTakeover):AwakeningAdapter.on_battle_failed(task)
            self.assertEqual(json.loads(task.failure_file.read_text()),{'orochi:6':'initial'})
        battle=SimpleNamespace(device=Mock(),screenshot=Mock(),I_WIN='win',I_DE_WIN='de_win',I_FALSE='false',appear=lambda target,**kwargs:target=='false',on_battle_failed=Mock(side_effect=RequestHumanTakeover('stop')),appear_then_click=Mock())
        with self.assertRaises(RequestHumanTakeover):GeneralBattle.battle_wait(battle,False)
        battle.appear_then_click.assert_not_called()

    def test_training_preview_and_result_use_actual_level_regions(self):
        from tasks.BeginnerQuest.training import training_preview,training_result
        boxes=[box('LV.20/25',711,552),box('Lv.25/25',925,553),box('1500',764,651),box('1660000',968,40)]
        self.assertEqual(training_preview(boxes),({'before':(20,25),'after':(25,25)},1500))
        self.assertEqual(training_result([box('Lv.20',787,258),box('Lv.25',957,258)]),(20,25))
        self.assertIsNone(training_result([box('Lv.20',787,258)]))

    def test_training_spend_is_rejected_when_target_or_coin_changes(self):
        from tasks.BeginnerQuest.training import TrainingAdapter
        for target,coin in [('LV.24/25','1500'),('LV.25/25','2500')]:
            task=object.__new__(TrainingAdapter)
            task._read=Mock(return_value=[box('式神升级',187,43),box('LV.20/25',711,552),box(target,925,553),box(coin,764,651)])
            task._tap=Mock()
            with self.assertRaises(RequestHumanTakeover):task.commit_preview((20,25),(25,25),[('blue',13),('red',1)],1500)
            task._tap.assert_not_called()

    def test_food_level_templates_distinguish_one_from_thirteen(self):
        import cv2
        one=cv2.imread('tasks/BeginnerQuest/templates/food_level_1.png')
        thirteen=cv2.imread('tasks/BeginnerQuest/templates/food_level_13.png')
        self.assertIsNotNone(one)
        self.assertIsNotNone(thirteen)
        self.assertLess(cv2.matchTemplate(one,thirteen,cv2.TM_CCOEFF_NORMED).max(),.95)

    def test_borrowed_card_is_not_confused_with_on_field(self):
        from tasks.BeginnerQuest.borrowing import observe_borrow_choice
        boxes=[box('麓铭大岳丸',676,582),box('使用中',346,515),box('待宵姑获鸟',346,582)]
        self.assertFalse(observe_borrow_choice(boxes,'麓铭大岳丸').borrowed)
        boxes.append(box('使用中',676,515))
        self.assertTrue(observe_borrow_choice(boxes,'麓铭大岳丸').borrowed)
        self.assertIsNone(observe_borrow_choice(boxes,'阿修罗'))

    def test_leveling_stops_at_verified_40_without_extra_battle(self):
        import tempfile
        from pathlib import Path
        from tasks.BeginnerQuest.leveling import LevelingRunner
        task=SimpleNamespace(config=SimpleNamespace(config_name='test'),device=SimpleNamespace(image=np.zeros((720,1280,3),np.uint8),screenshot=Mock(return_value=np.zeros((720,1280,3),np.uint8))),goto_page=Mock(),screenshot=Mock())
        with tempfile.TemporaryDirectory() as directory,patch('tasks.BeginnerQuest.leveling.Path',side_effect=lambda p:Path(directory)/p),patch('tasks.BeginnerQuest.leveling.read_player_level',side_effect=[28,40]),patch('tasks.BeginnerQuest.leveling.read_stamina',return_value=648),patch('tasks.BeginnerQuest.leveling.run_existing') as run:
            result=LevelingRunner.run_to(task,10,target=40)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(run.call_count,1)
        self.assertTrue(run.call_args.kwargs['xp_only'])

    def test_verified_target_stops_even_if_unlock_overlay_hides_stamina(self):
        import tempfile
        from pathlib import Path
        from tasks.BeginnerQuest.leveling import LevelingRunner
        task=SimpleNamespace(config=SimpleNamespace(config_name='test'),device=SimpleNamespace(image=np.zeros((720,1280,3),np.uint8)),goto_page=Mock(),screenshot=Mock())
        with tempfile.TemporaryDirectory() as directory,patch('tasks.BeginnerQuest.leveling.Path',side_effect=lambda p:Path(directory)/p),patch('tasks.BeginnerQuest.leveling.read_player_level',return_value=31),patch('tasks.BeginnerQuest.leveling.read_stamina',return_value=None),patch('tasks.BeginnerQuest.leveling.run_existing') as run:
            result=LevelingRunner.run_to(task,13,target=31)
        self.assertEqual(result['status'],'complete')
        run.assert_not_called()

    def test_leveling_reserves_stamina_without_buying_or_starting(self):
        import tempfile
        from pathlib import Path
        from tasks.BeginnerQuest.leveling import LevelingRunner
        task=SimpleNamespace(config=SimpleNamespace(config_name='test'),device=SimpleNamespace(image=np.zeros((720,1280,3),np.uint8),screenshot=Mock(return_value=np.zeros((720,1280,3),np.uint8))),goto_page=Mock(),screenshot=Mock())
        with tempfile.TemporaryDirectory() as directory,patch('tasks.BeginnerQuest.leveling.Path',side_effect=lambda p:Path(directory)/p),patch('tasks.BeginnerQuest.leveling.read_player_level',return_value=28),patch('tasks.BeginnerQuest.leveling.read_stamina',return_value=59),patch('tasks.BeginnerQuest.leveling.run_existing') as run:
            result=LevelingRunner.run_to(task,10)
        self.assertEqual(result['status'],'low_stamina')
        run.assert_not_called()

    def test_normal_selector_can_recover_from_merged_fullscreen_ocr(self):
        from tasks.BeginnerQuest.exploration_hard import ExplorationNormalAdapter
        from tasks.Exploration.script_task import ScriptTask as ExplorationTask
        image=np.zeros((720,1280,3),np.uint8);image[231:260,20:180]=(200,40,40)
        task=object.__new__(ExplorationNormalAdapter)
        task.config=SimpleNamespace(exploration=SimpleNamespace(exploration_config=SimpleNamespace(exploration_level='第十章')))
        task.device=SimpleNamespace(image=image,click=Mock());task.screenshot=Mock()
        with patch.object(ExplorationTask,'open_expect_level'),patch('tasks.BeginnerQuest.exploration_hard.get_ocr_model') as ocr,patch('tasks.BeginnerQuest.exploration_hard.time.sleep'):
            ocr.return_value.detect_and_ocr.side_effect=[[box('第十章',200,30)],[box('开普通',210,135)]]
            task.open_expect_level()
        self.assertEqual(task.device.click.call_args.args,(80,245))

    def test_leveling_errors_persist_stopped_status(self):
        import tempfile,json
        from pathlib import Path
        from tasks.BeginnerQuest.leveling import LevelingRunner
        task=SimpleNamespace(config=SimpleNamespace(config_name='test'),device=SimpleNamespace(image=np.zeros((720,1280,3),np.uint8),screenshot=Mock(return_value=np.zeros((720,1280,3),np.uint8))),goto_page=Mock(),screenshot=Mock())
        with tempfile.TemporaryDirectory() as directory,patch('tasks.BeginnerQuest.leveling.Path',side_effect=lambda p:Path(directory)/p),patch('tasks.BeginnerQuest.leveling.read_player_level',return_value=29),patch('tasks.BeginnerQuest.leveling.read_stamina',return_value=638),patch('tasks.BeginnerQuest.leveling.run_existing',side_effect=ValueError('selector')):
            with self.assertRaises(ValueError):LevelingRunner.run_to(task,10)
            state=json.loads((Path(directory)/'log/beginner_quest/test/leveling.json').read_text())
        self.assertEqual(state['status'],'stopped_error')
        self.assertIn('selector',state['reason'])

    def test_first_clear_requires_boss_victory_and_preserves_40_target(self):
        import tempfile
        from pathlib import Path
        from tasks.BeginnerQuest.first_clears import FirstClearRunner
        task=SimpleNamespace(config=SimpleNamespace(config_name='test'),device=SimpleNamespace(image=np.zeros((720,1280,3),np.uint8),screenshot=Mock(return_value=np.zeros((720,1280,3),np.uint8))),goto_page=Mock(),screenshot=Mock())
        for boss_wins in (0,1):
            with tempfile.TemporaryDirectory() as directory,patch('tasks.BeginnerQuest.first_clears.Path',side_effect=lambda p:Path(directory)/p),patch('tasks.BeginnerQuest.first_clears.read_player_level',side_effect=[29,30]),patch('tasks.BeginnerQuest.first_clears.read_stamina',return_value=580),patch('tasks.BeginnerQuest.first_clears.run_existing',return_value={'boss_wins':boss_wins,'chapter':10}) as run:
                if not boss_wins:
                    with self.assertRaises(RequestHumanTakeover):FirstClearRunner.run_route(task,[('normal',10)])
                else:
                    result=FirstClearRunner.run_route(task,[('normal',10),('hard',1)])
                    self.assertEqual(result['status'],'milestone_replan')
                    self.assertEqual(run.call_count,1)

    def test_unchanged_level_batches_request_replanning(self):
        import tempfile
        from pathlib import Path
        from tasks.BeginnerQuest.leveling import LevelingRunner
        task=SimpleNamespace(config=SimpleNamespace(config_name='test'),device=SimpleNamespace(image=np.zeros((720,1280,3),np.uint8),screenshot=Mock(return_value=np.zeros((720,1280,3),np.uint8))),goto_page=Mock(),screenshot=Mock())
        with tempfile.TemporaryDirectory() as directory,patch('tasks.BeginnerQuest.leveling.Path',side_effect=lambda p:Path(directory)/p),patch('tasks.BeginnerQuest.leveling.read_player_level',return_value=29),patch('tasks.BeginnerQuest.leveling.read_stamina',return_value=580),patch('tasks.BeginnerQuest.leveling.run_existing') as run:
            result=LevelingRunner.run_to(task,10,unchanged_limit=3)
        self.assertEqual(result['status'],'replan_needed')
        self.assertEqual(run.call_count,3)
