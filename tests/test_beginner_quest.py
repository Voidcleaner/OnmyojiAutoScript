import unittest
from types import SimpleNamespace
from unittest.mock import patch
import cv2
import numpy as np
from tasks.BeginnerQuest.vision import ellipsis_action, choose_text, template_action, movie_skip_action
from tasks.BeginnerQuest.script_task import ScriptTask
from tasks.BeginnerQuest.config import QuestOptions
from module.exception import RequestHumanTakeover


def box(text, x=800, y=550, score=.99):
    return SimpleNamespace(ocr_text=text, score=score,
                           box=np.array([[x-15,y-10],[x+15,y-10],[x+15,y+10],[x-15,y+10]]))


class BeginnerQuestTests(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((720,1280,3),np.uint8)
        self.task = ScriptTask(SimpleNamespace(beginner_quest=SimpleNamespace(quest_options=QuestOptions())),None)

    def decide(self, boxes):
        with patch('tasks.BeginnerQuest.script_task.get_ocr_model') as model, patch.object(self.task,'templates',return_value=None):
            model.return_value.detect_and_ocr.return_value=boxes
            return self.task.decide(self.image)

    def test_three_dots_need_circle(self):
        for x in (388,400,412):
            cv2.circle(self.image,(x,250),4,(240,240,240),-1)
        self.assertIsNone(ellipsis_action(self.image))
        cv2.circle(self.image,(400,250),26,(240,200,120),3)
        self.assertEqual(ellipsis_action(self.image).point,(400,250))

    def test_chat_skip_is_not_a_button(self):
        self.assertIsNone(self.decide([box('跳过',800,80)]))

    def test_dialog_skip(self):
        self.assertEqual(self.decide([box('跳过')]).name,'skip')

    def test_confirm_requires_skip_context(self):
        self.assertIsNone(self.decide([box('确定')]))
        self.task.skip_pending=True
        self.assertEqual(self.decide([box('确定')]).name,'confirm_skip')

    def test_resource_prompt_stops(self):
        with self.assertRaises(RequestHumanTakeover):
            self.decide([box('体力不足')])

    def test_unverified_borrowed_team_blocks_ready(self):
        self.task.borrow_seen=True
        with self.assertRaises(RequestHumanTakeover):
            self.decide([box('准备',1150,600)])

    def test_prepare_can_continue_verified_team(self):
        self.task.borrow_seen=True
        self.task.team_verified=True
        self.assertEqual(self.decide([box('准备',1150,600)]).name,'prepare')

    def test_ocr_low_confidence_and_wrong_region_rejected(self):
        self.assertIsNone(choose_text([box('借用',score=.3)],('借用',),(200,100,1200,700),'borrow'))

    def test_movie_skip_requires_triangle_and_bar(self):
        cv2.fillPoly(self.image,[np.array([[1160,30],[1160,54],[1180,42]])],(255,255,255))
        self.assertIsNone(movie_skip_action(self.image))
        cv2.rectangle(self.image,(1185,30),(1189,54),(255,255,255),-1)
        self.assertEqual(movie_skip_action(self.image).name,'skip_movie')

    def test_clipped_npc_circle(self):
        cv2.circle(self.image,(1277,250),26,(240,200,120),3)
        for x in (1265,1277):
            cv2.circle(self.image,(x,250),4,(240,240,240),-1)
        self.assertEqual(ellipsis_action(self.image).point,(1270,250))

    def test_long_privacy_text_is_not_a_purchase_prompt(self):
        self.assertIsNone(self.decide([box('这是很长的隐私提示说明，包括充值记录、设备信息以及个性化服务的详细文字')]))

    def test_new_feature_popup_can_be_closed(self):
        self.assertEqual(self.decide([box('点击空白处关闭',640,680)]).name,'continue')


if __name__=='__main__':
    unittest.main()
