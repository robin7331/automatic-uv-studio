from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class CheckIfOnline(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Check if online", **kwargs)

    def run(self, tab_index=0):
        super().run()

        self.click_canvas_index(index=tab_index)

        online = pyautogui.locateOnScreen("images/online.png", confidence=0.9)
        if not online:
            return False

        return True
