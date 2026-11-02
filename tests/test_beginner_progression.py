import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tasks.BeginnerQuest.progression import run_level_gate


class ProgressionTests(unittest.TestCase):
    def test_insufficient_free_stamina_never_enters_story(self):
        with patch('tasks.BeginnerQuest.progression.LevelingRunner') as leveling, patch('tasks.BeginnerQuest.progression.ScriptTask') as story:
            leveling.return_value.run_to.return_value={'status':'low_stamina','player_level':33}
            result=run_level_gate(None,None,17,35)
            self.assertEqual(result['story'],'not_started')
            story.assert_not_called()

    def test_story_failure_restores_persistent_task_limits(self):
        options=SimpleNamespace(max_seconds=90,max_actions=50,max_battles=3)
        config=SimpleNamespace(beginner_quest=SimpleNamespace(quest_options=options))
        with patch('tasks.BeginnerQuest.progression.LevelingRunner') as leveling, patch('tasks.BeginnerQuest.progression.ScriptTask') as story:
            leveling.return_value.run_to.return_value={'status':'complete','player_level':35}
            story.return_value.run.side_effect=RuntimeError('unknown screen')
            with self.assertRaises(RuntimeError):run_level_gate(config,None,17,35)
        self.assertEqual((options.max_seconds,options.max_actions,options.max_battles),(90,50,3))
