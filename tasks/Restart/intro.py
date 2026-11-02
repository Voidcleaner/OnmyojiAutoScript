"""Login-only startup movie controls; one wake tap per login attempt."""
import numpy as np
from tasks.BeginnerQuest.vision import Action, choose_text, movie_skip_action


class LoginIntro:
    def __init__(self):
        self.woken = False

    def decide(self, image, boxes=(), known_screen=False):
        if known_screen:
            return None
        action = movie_skip_action(image) or choose_text(
            boxes, ('点击屏幕跳过', '点击跳过', '跳过'), (900, 0, 1280, 130), 'login_skip')
        if action:
            return action
        # The startup movie hides its controls until the first tap. Only do this
        # once, on a nonblank unknown screen, inside the login flow.
        if not self.woken and float(np.std(image)) > 15:
            self.woken = True
            return Action('login_movie_wake', (640, 360))
        return None
