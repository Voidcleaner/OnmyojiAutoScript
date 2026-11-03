import unittest
from types import SimpleNamespace
import numpy as np
from tasks.ActivityShikigami.feiyu import boosted_count

def box(text,x=170,y=590):
    return SimpleNamespace(ocr_text=text,score=.99,box=np.array([[x,y],[x,y],[x,y],[x,y]]))

class FeiyuTests(unittest.TestCase):
    def test_training_counter_requires_daily_reward_label(self):
        self.assertEqual(boosted_count([box('每日前5次挑战掉落提升（3/5）')]),3)
        self.assertEqual(boosted_count([box('每日5/5掉落提升')]),5)
        self.assertIsNone(boosted_count([box('队伍3/5')]))

    def test_unknown_counter_never_defaults_to_unused(self):
        self.assertIsNone(boosted_count([box('每日前5次挑战掉落提升')]))

    def test_courtyard_ocr_fallback_requires_multiple_footer_labels_and_avatar(self):
        from unittest.mock import Mock,patch
        from tasks.GameUi.default_pages import modern_courtyard
        task=SimpleNamespace(appear=Mock(side_effect=[True,False]),device=SimpleNamespace(image=None))
        with patch('module.ocr.models.get_ocr_model') as model,patch('tasks.BeginnerQuest.planner.read_player_level',return_value=36):
            model.return_value.detect_and_ocr.return_value=[box('阴阳术',1000,670),box('式神录',1140,670),box('商店',690,670)]
            self.assertTrue(modern_courtyard(task))
        task.appear=Mock(side_effect=[True,False])
        with patch('module.ocr.models.get_ocr_model') as model,patch('tasks.BeginnerQuest.planner.read_player_level',return_value=36):
            model.return_value.detect_and_ocr.return_value=[box('商店',690,670)]
            self.assertFalse(modern_courtyard(task))

    def test_unknown_event_panel_does_not_challenge(self):
        from unittest.mock import Mock
        from module.exception import RequestHumanTakeover
        from tasks.ActivityShikigami.feiyu import FeiyuTraining
        task=object.__new__(FeiyuTraining)
        task._read=Mock(return_value=[box('商城')]);task._tap=Mock()
        with self.assertRaises(RequestHumanTakeover):task.run_event_battle()
        task._tap.assert_not_called()

    def test_continuous_target_stops_before_story_or_farming(self):
        from unittest.mock import Mock,patch
        from tasks.BeginnerQuest.continuous import ContinuousProgression
        task=object.__new__(ContinuousProgression)
        task.device=SimpleNamespace(image=None);task.goto_page=Mock();task.screenshot=Mock()
        task._record=Mock(return_value={'status':'complete'});task.run_to=Mock()
        with patch('tasks.BeginnerQuest.continuous.read_player_level',return_value=40):
            self.assertEqual(task.run(15,target=40)['status'],'complete')
        task.run_to.assert_not_called()

    def test_continuous_expired_budget_sends_no_input(self):
        from unittest.mock import Mock,patch
        from tasks.BeginnerQuest.continuous import ContinuousProgression
        task=object.__new__(ContinuousProgression)
        task.goto_page=Mock();task._record=Mock(return_value={'status':'time_limit'})
        with patch('tasks.BeginnerQuest.continuous.time.monotonic',side_effect=[0,61]):
            self.assertEqual(task.run(15,max_seconds=60)['status'],'time_limit')
        task.goto_page.assert_not_called()
