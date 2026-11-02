"""Reusable leveling milestone followed by bounded courtyard story progression."""
from module.exception import TaskEnd
from tasks.BeginnerQuest.leveling import LevelingRunner
from tasks.BeginnerQuest.script_task import ScriptTask


def run_level_gate(config, device, chapter, target, *, difficulty='hard',
                   min_stamina=30, max_batches=15, story_seconds=600):
    """Farm a verified chapter, then resume story only after verified level gain.

    Insufficient free stamina returns without buying resources. Story retains
    its existing loss, unknown-screen and battle-resume safeguards. Reaching
    this milestone is not proof that the account reached the overall goal.
    """
    if not 1 <= story_seconds <= 1800:
        raise ValueError('Story time budget must be between 1 and 1800 seconds')
    result = LevelingRunner(config, device).run_to(
        chapter, target=target, max_batches=max_batches,
        min_stamina=min_stamina, xp_only=False, difficulty=difficulty)
    if result['status'] != 'complete':
        return {'leveling': result, 'story': 'not_started'}
    options = config.beginner_quest.quest_options
    previous = (options.max_seconds, options.max_actions, options.max_battles)
    try:
        options.max_seconds = story_seconds
        options.max_actions = 400
        options.max_battles = 30
        runner = ScriptTask(config, device)
        reason = None
        try:
            runner.run()
        except TaskEnd as exc:
            reason = str(exc)
        return {'leveling': result,
                'story': 'resume_battle' if runner.battle_pending or runner.prepare_clicked else 'replan_needed',
                'story_reason': reason}
    finally:
        options.max_seconds, options.max_actions, options.max_battles = previous
