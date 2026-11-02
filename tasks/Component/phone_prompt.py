"""Dismiss optional phone association through Go bind -> Cancel, never submit."""
import time
from tasks.BeginnerQuest.vision import choose_text


class PhoneBindingFlow:
    def __init__(self):
        self.opened_at = None

    def decide(self, boxes, now=None):
        now = time.monotonic() if now is None else now
        if self.opened_at is not None and now-self.opened_at>60:
            self.opened_at=None
        central=[b for b in boxes if 110<b.box[:,1].mean()<650]
        context=any(any(w in b.ocr_text for w in ('关联手机','绑定手机','手机号码','手机号','验证码')) for b in central)
        if not context:return None
        cancel=choose_text(boxes,('取消','暂不绑定','暂不关联'),(200,180,1100,700),'cancel_phone_binding')
        binding_form=any(any(w in b.ocr_text for w in ('手机号','手机号码','验证码')) for b in central)
        if (self.opened_at is not None or binding_form) and cancel:
            self.opened_at=None
            return cancel
        go=choose_text(boxes,('前往绑定','前往关联'),(200,180,1100,700),'open_phone_binding')
        if go:
            self.opened_at=now
            return go
        return None


def handle_phone_prompt(task):
    from module.ocr.models import get_ocr_model
    if not hasattr(task,'_phone_binding_flow'):
        task._phone_binding_flow=PhoneBindingFlow()
    handled=False
    for _ in range(3):
        boxes=get_ocr_model().detect_and_ocr(task.device.image)
        action=task._phone_binding_flow.decide(boxes)
        if not action:break
        task.device.click(*action.point,control_check=False,control_name=action.name)
        handled=True
        time.sleep(.8)
        task.device.screenshot()
    return handled
