"""Exact bottom-screen continue prompts shared by login/novice/settlement flows."""
from tasks.BeginnerQuest.vision import choose_text


def handle_continue_prompt(task):
    from module.ocr.models import get_ocr_model
    boxes=get_ocr_model().detect_and_ocr(task.device.image[500:720,200:1250])
    action=choose_text(boxes,('点击屏幕继续','点击任意位置继续','点击空白处关闭'),(0,0,1050,220),'continue_prompt')
    if not action:return False
    task.device.click(action.point[0]+200,action.point[1]+500,control_check=False,control_name=action.name)
    return True
