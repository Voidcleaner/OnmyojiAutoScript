"""Exact bottom-screen continue prompts shared by login/novice/settlement flows."""
from tasks.BeginnerQuest.vision import choose_text


def handle_continue_prompt(task):
    from module.ocr.models import get_ocr_model
    boxes=get_ocr_model().detect_and_ocr(task.device.image[400:720,200:1250])
    action=choose_text(boxes,('点击屏幕继续','点击任意位置继续','点击空白处关闭','点击任意位置关闭'),(0,0,1050,320),'continue_prompt')
    if not action:return False
    from tasks.BeginnerQuest.vision import pink_close_action
    close=pink_close_action(task.device.image)
    if close:
        task.device.click(*close.point,control_check=False,control_name=close.name)
        return True
    task.device.click(action.point[0]+200,action.point[1]+400,control_check=False,control_name=action.name)
    return True
