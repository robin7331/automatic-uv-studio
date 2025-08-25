from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class CheckIfIdle(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Check if idle", **kwargs)

    def run(self):
        super().run()

        # click the printers tab
        self.click_machine()

        # Check if the printer is idle
        online = pyautogui.locateOnScreen("images/idle.png", confidence=0.9)
        if not online:
            return False

        return True
