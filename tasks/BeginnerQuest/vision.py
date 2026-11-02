"""Deterministic selectors, separate from game input for replay tests."""
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np


@dataclass
class Action:
    name: str
    point: tuple
    score: float = 1.0


def template_action(rgb, filename, name, threshold=.86, region=(0, 110, 1280, 720)):
    template = cv2.imread(str(filename))
    if template is None or float(np.max(np.std(template.astype(float), axis=(0, 1)))) < 6:
        return None
    x1, y1, x2, y2 = region
    search = cv2.cvtColor(rgb[y1:y2, x1:x2], cv2.COLOR_RGB2BGR)
    h, w = template.shape[:2]
    if search.shape[0] < h or search.shape[1] < w:
        return None
    scoremap = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, pos = cv2.minMaxLoc(scoremap)
    if not np.isfinite(score) or score < threshold:
        return None
    return Action(name, (x1 + pos[0] + w // 2, y1 + pos[1] + h // 2), score)


def choose_text(boxes, words, region, name):
    x1, y1, x2, y2 = region
    for word in words:
        for item in boxes:
            text = item.ocr_text.replace(' ', '').strip('—-~·•:：。.!！')
            box = item.box
            x, y = np.mean(box, axis=0)
            if item.score >= .75 and text == word and x1 <= x <= x2 and y1 <= y <= y2:
                return Action(name, (int(x), int(y)), float(item.score))
    return None


def ellipsis_action(rgb, excluded_regions=()):
    """Find three aligned light dots inside a lit circular NPC marker."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    mask = cv2.inRange(gray, 170, 255)
    n, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    dots = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if 3 <= w <= 11 and 3 <= h <= 11 and 7 <= area <= 85 and 110 < y < 620:
            cx,cy=centers[i]
            if not any(x1<=cx<=x2 and y1<=cy<=y2 for x1,y1,x2,y2 in excluded_regions):
                dots.append(centers[i])
    for x, y in dots:
        row = sorted((cx, cy) for cx, cy in dots if abs(cy-y) <= 3 and x-2 <= cx <= x+38)
        if len(row) == 2 and row[0][0] > 1240 and 7 <= row[1][0]-row[0][0] <= 18:
            cx, cy = int(row[1][0]), int(row[1][1])
            padded = cv2.copyMakeBorder(gray, 30, 30, 30, 30, cv2.BORDER_CONSTANT)
            patch = padded[cy:cy+61, cx:cx+61]
            yy, xx = np.ogrid[-30:31, -30:31]
            ring = ((xx*xx+yy*yy) >= 22**2) & ((xx*xx+yy*yy) <= 29**2)
            if float(np.mean(patch[ring] > 145)) >= .10:
                return Action('talk', (min(cx, 1270), cy), .85)
        if len(row) < 3:
            continue
        a, b, c = row[:3]
        if not (7 <= b[0]-a[0] <= 18 and 7 <= c[0]-b[0] <= 18):
            continue
        cx, cy = int(b[0]), int(b[1])
        if cx < 35 or cx > 1245 or cy < 35 or cy > 685:
            continue
        patch = gray[cy-30:cy+31, cx-30:cx+31]
        yy, xx = np.ogrid[-30:31, -30:31]
        ring = ((xx*xx+yy*yy) >= 22**2) & ((xx*xx+yy*yy) <= 29**2)
        # Roof lights and other horizontal dot rows are not circular markers.
        angles=np.arctan2(yy,xx)
        sectors=[ring & (angles>=a) & (angles<a+np.pi/4)
                 for a in np.arange(-np.pi,np.pi,np.pi/4)]
        coverage=sum(float(np.mean(patch[sector]>145))>=.15 for sector in sectors)
        if coverage>=6 and float(np.mean(patch[ring] > 145)) >= .20 and patch[30, 30] > 160:
            return Action('talk', (cx, cy), .9)
    return None


def movie_skip_action(rgb):
    """Detect a filled right-facing triangle followed by a vertical bar (>│)."""
    image = rgb[0:130, 900:1280]
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, (0, 0, 185), (179, 120, 255))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        if not (10 <= h <= 40 and 7 <= w <= 35 and .35*w*h <= area <= .8*w*h):
            continue
        poly = cv2.approxPolyDP(contour, .06*cv2.arcLength(contour,True),True)
        if len(poly) != 3:
            continue
        pts = poly[:,0,:]
        tip = pts[np.argmax(pts[:,0])]
        if not y+.2*h <= tip[1] <= y+.8*h:
            continue
        for bar in contours:
            bx, by, bw, bh = cv2.boundingRect(bar)
            if (1 <= bx-(x+w) <= 18 and 2 <= bw <= 7 and .7*h <= bh <= 1.3*h
                    and abs((by+bh/2)-(y+h/2)) <= 5):
                return Action('skip_movie',(900+x+w//2,y+h//2),.92)
    return None


def prepare_is_enabled(image, point):
    x,y=point
    patch=image[max(0,y-32):min(720,y+32),max(0,x-32):min(1280,x+32)]
    return patch.size > 0 and float(cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)[:,:,2].mean()) >= 95


def read_courtyard_story_gate(image):
    """Read the locked story marker only, excluding avatar/shikigami levels."""
    import re
    from module.ocr.models import get_ocr_model
    crop=cv2.resize(image[315:395,320:455],None,fx=3,fy=3)
    levels=[]
    for box in get_ocr_model().detect_and_ocr(crop):
        match=re.fullmatch(r'Lv[.:：·]?(\d{1,2})',box.ocr_text.replace(' ',''),re.I)
        if box.score>=.75 and match and 1<=int(match[1])<=60:
            levels.append(int(match[1]))
    return levels[0] if len(levels)==1 else None
