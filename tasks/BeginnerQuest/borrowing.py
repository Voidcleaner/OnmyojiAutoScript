"""Free novice borrowing; acquiring a card never implies it is on the field."""
import time
from dataclasses import dataclass
from module.exception import RequestHumanTakeover
from tasks.BeginnerQuest.novice_hub import NoviceHub
from tasks.GameUi.page import page_beginner_borrow


@dataclass(frozen=True)
class BorrowChoice:
    name: str
    point: tuple
    borrowed: bool


def observe_borrow_choice(boxes,name):
    names=[b for b in boxes if b.score>=.75 and b.ocr_text==name
           and 270<b.box[:,0].mean()<1220 and 550<b.box[:,1].mean()<610]
    if len(names)!=1:return None
    x,y=map(int,names[0].box.mean(axis=0))
    borrowed=any(b.ocr_text=='使用中' and b.score>=.75 and abs(b.box[:,0].mean()-x)<55
                 and 480<b.box[:,1].mean()<550 for b in boxes)
    return BorrowChoice(name,(x,y-100),borrowed)


class BorrowingAdapter(NoviceHub):
    def borrow(self,name):
        self.goto_page(page_beginner_borrow)
        boxes=self._read();choice=observe_borrow_choice(boxes,name)
        if choice is None:raise RequestHumanTakeover('Requested support card is not visible; do not select a different one')
        if choice.borrowed:return {'name':name,'borrowed':True,'on_field_verified':False}
        if sum(b.ocr_text=='使用中' for b in boxes)>=3:
            raise RequestHumanTakeover('All novice borrowing slots are occupied; do not replace a card automatically')
        self._tap(choice.point)
        for _ in range(8):
            boxes=self._read();choice=observe_borrow_choice(boxes,name)
            if choice and choice.borrowed:
                # Safe empty margin, outside every character card. Closes the
                # one-time borrowing reward if it appeared, without another borrow.
                self._tap((220,600))
                return {'name':name,'borrowed':True,'on_field_verified':False}
            time.sleep(.5)
        raise RequestHumanTakeover('Borrowing was clicked once but not verified; inspect before retry')
