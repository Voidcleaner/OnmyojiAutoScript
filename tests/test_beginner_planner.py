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
