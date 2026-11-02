"""Dismiss optional guild enrollment prompts without applying or joining."""
def handle_guild_join_prompt(task):
    from module.ocr.models import get_ocr_model
    from tasks.BeginnerQuest.vision import choose_text
    boxes=get_ocr_model().detect_and_ocr(task.device.image)
    text=''.join(b.ocr_text for b in boxes if 180<b.box[:,1].mean()<600)
    if not ('暂未加入' in text and ('阴阳寮' in text or '阴阳' in text)):
        return False
    action=choose_text(boxes,('取消',),(300,350,750,550),'CANCEL_OPTIONAL_GUILD')
    if not action:return False
    task.device.click(*action.point,control_check=False,control_name=action.name)
    task.device.click_record_clear()
    # This route requires guild membership; avoid reopening it in this session.
    task.navigator.edge_penalties['page_exploration->page_realm_raid']=100
    return True


def handle_cosmetic_activation(task,boxes=None):
    from module.ocr.models import get_ocr_model
    from tasks.BeginnerQuest.vision import choose_text
    if boxes is None:boxes=get_ocr_model().detect_and_ocr(task.device.image)
    if not any('是否立即启用' in b.ocr_text for b in boxes):return False
    action=choose_text(boxes,('取消',),(300,350,750,550),'CANCEL_COSMETIC_ACTIVATION')
    if not action:return False
    task.device.click(*action.point,control_check=False,control_name=action.name)
    return True
