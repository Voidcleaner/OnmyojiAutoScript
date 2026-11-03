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
