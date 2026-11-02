"""Bounded scene panning, following Exploration's compare-and-reverse approach."""
import random
import cv2
import numpy as np


class SceneSearch:
    def __init__(self, limit=8):
        self.limit = limit
        self.reset()

    def reset(self):
        self.count = self.unchanged = 0
        self.direction = 1
        self.reversed = False
        self.before = None

    @staticmethod
    def fingerprint(image):
        # Ignore scrolling chat, ground characters and HUD. Blur animated details.
        return cv2.resize(cv2.GaussianBlur(image[130:260, 200:1080], (15, 15), 0), (88, 13)).astype(float)

    def next_drag(self, image, rng=random):
        if self.before is not None:
            difference = np.mean(np.abs(self.fingerprint(image) - self.before))
            self.unchanged = self.unchanged + 1 if difference < 5 else 0
            if self.unchanged >= 2:
                if self.reversed:
                    return None
                self.direction *= -1
                self.reversed = True
                self.unchanged = 0
        # Animated scenery can keep pixel differences high at an edge. Reserve
        # the remaining budget for the opposite direction regardless of motion.
        if not self.reversed and self.count >= (self.limit + 2) // 3:
            self.direction *= -1
            self.reversed = True
            self.unchanged = 0
        if self.count >= self.limit:
            return None
        self.before = self.fingerprint(image)
        self.count += 1
        # Same upper background lane as Exploration; avoid NPCs and bottom UI.
        left, right = rng.randint(390, 440), rng.randint(1060, 1110)
        y = rng.randint(140, 160)
        return ((right, y), (left, y + rng.randint(-4, 4))) if self.direction == 1 else ((left, y), (right, y + rng.randint(-4, 4)))


def click_point(point, radius, rng=random):
    return tuple(max(1, min(bound, value + rng.randint(-radius, radius)))
                 for value, bound in zip(point, (1278, 718)))
