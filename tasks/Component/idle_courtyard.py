"""Exit the game's idle courtyard display without opening profile or chat."""
from module.atom.image import RuleImage

IDLE_COURTYARD=RuleImage(roi_front=(25,20,275,65),roi_back=(0,0,320,110),threshold=.9,
                         method='Template matching',file='./tasks/GlobalGame/ui/ui_idle_courtyard.png')


def handle_idle_courtyard(task):
    if not task.appear(IDLE_COURTYARD):return False
    task.device.click(58,55,control_check=False,control_name='EXIT_IDLE_COURTYARD')
    return True
