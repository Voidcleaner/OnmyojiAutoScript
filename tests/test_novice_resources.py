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
