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

    def test_map_without_battles_is_not_complete_before_total(self):
        from unittest.mock import Mock
        from tasks.ActivityShikigami.feiyu import FeiyuTraining
        task=object.__new__(FeiyuTraining)
        task._settled_map_boxes=Mock(return_value=[box('探索进度27/28',100,124)])
        task._tap=Mock()
        self.assertEqual(task.run_map_duels()['status'],'story_node_required')
        task._tap.assert_not_called()

    def test_map_complete_requires_verified_total(self):
        from unittest.mock import Mock
        from tasks.ActivityShikigami.feiyu import FeiyuTraining
        task=object.__new__(FeiyuTraining)
        task._settled_map_boxes=Mock(return_value=[box('探索进度28/28',100,124)])
        task._tap=Mock()
        self.assertEqual(task.run_map_duels()['status'],'map_complete')
        task._tap.assert_not_called()

    def test_map_arrow_is_required_to_be_unambiguous(self):
        import cv2
        from tasks.ActivityShikigami.feiyu import next_map_arrow
        image=np.zeros((720,1280,3),dtype=np.uint8)
        arrow=np.array([[610,180],[620,180],[620,200],[630,200],[615,220],[600,200],[610,200]])
        cv2.fillPoly(image,[arrow],(255,220,0))
        self.assertIsNotNone(next_map_arrow(image))
        cv2.fillPoly(image,[arrow+np.array([200,0])],(255,220,0))
        self.assertIsNone(next_map_arrow(image))

    def test_reward_tabs_are_not_mistaken_for_a_popup(self):
        from unittest.mock import Mock
        from tasks.ActivityShikigami.feiyu import FeiyuTraining
        task=object.__new__(FeiyuTraining);task._dismiss=Mock()
        self.assertFalse(task._event_cosmetic_popup([box('成就',1193,346),box('头像框',800,250)]))
        task._dismiss.assert_not_called()

    def test_gained_unit_overlay_takes_priority_over_underlying_reward_tabs(self):
        from unittest.mock import Mock
        from tasks.ActivityShikigami.feiyu import FeiyuTraining
        task=object.__new__(FeiyuTraining);task._dismiss=Mock(return_value=True)
        self.assertTrue(task._event_cosmetic_popup([box('获得',358,123),box('成就',1193,346)]))
        task._dismiss.assert_called_once()
