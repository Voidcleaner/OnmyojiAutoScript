import unittest
from types import SimpleNamespace
from tasks.BeginnerQuest.mentorship import guardian_remaining,paired_guardian_room

def boxes(*words):return [SimpleNamespace(ocr_text=w,score=.99) for w in words]

class MentorshipTests(unittest.TestCase):
    def test_daily_allowance_is_explicit(self):
        self.assertEqual(guardian_remaining(boxes('剩余挑战次数：5/5')),5)
        self.assertEqual(guardian_remaining(boxes('剩余挑战次数：0/5')),0)
        self.assertIsNone(guardian_remaining(boxes('完成20次守护历练（10/20）')))

    def test_never_treat_solo_or_other_dungeon_as_ready(self):
        self.assertFalse(paired_guardian_room(boxes('目标守护历练','师父','邀请后辈'),'师父','徒弟'))
        self.assertFalse(paired_guardian_room(boxes('师父','徒弟','御魂'),'师父','徒弟'))
        self.assertTrue(paired_guardian_room(boxes('协战队伍','目标守护历练','师父','徒弟'),'师父','徒弟'))

    def test_guardian_overview_is_not_a_battle_room(self):
        self.assertFalse(paired_guardian_room(boxes('前辈之守护','师父','徒弟','完成20次守护历练'),'师父','徒弟'))

    def test_continue_prompt_resumes_known_pair_invitation(self):
        import numpy as np
        from unittest.mock import Mock
        from tasks.BeginnerQuest.mentorship import MentorshipRunner
        def b(text,x,y):return SimpleNamespace(ocr_text=text,score=.99,box=np.array([[x,y]]*4))
        runner=object.__new__(MentorshipRunner)
        runner.teacher=SimpleNamespace(_read=Mock(return_value=[b('是否邀请队友继续进行战斗？',640,305),b('确定',755,438)]),device=Mock())
        runner._invitation_sent=False
        self.assertIsNone(runner._open_room())
        self.assertTrue(runner._invitation_sent)
        runner.teacher.device.click.assert_called_once()

    def test_unrelated_confirmation_never_sends_invitation(self):
        from unittest.mock import Mock
        from module.exception import RequestHumanTakeover
        from tasks.BeginnerQuest.mentorship import MentorshipRunner
        runner=object.__new__(MentorshipRunner)
        runner.teacher=SimpleNamespace(_read=Mock(return_value=boxes('购买体力','确定')),device=Mock())
        runner.teacher_name='师父';runner.pupil_name='徒弟'
        with self.assertRaises(RequestHumanTakeover):runner._open_room()
        runner.teacher.device.click.assert_not_called()

    def test_daily_complete_requires_zero_remaining_from_game(self):
        from unittest.mock import Mock,patch
        from tasks.BeginnerQuest.mentorship import MentorshipRunner
        for remaining,expected in [(0,'daily_complete'),(2,'batch_complete'),(None,'batch_complete')]:
            with self.subTest(remaining=remaining):
                runner=object.__new__(MentorshipRunner)
                observed=boxes('协同')+(boxes(f'剩余挑战次数：{remaining}/5') if remaining is not None else [])
                runner.teacher=SimpleNamespace(_read=Mock(return_value=boxes('协同')),_tap=Mock(return_value=observed))
                runner.pupil=SimpleNamespace(screenshot=Mock(),device=SimpleNamespace(image=None))
                runner._save=Mock()
                with patch('tasks.GameUi.default_pages.modern_courtyard',return_value=False):runner._conclude(3,5)
                self.assertEqual(runner._save.call_args.args[0],expected)
