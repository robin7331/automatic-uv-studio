from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class CheckIfLowInk(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Check if low ink", **kwargs)

    def run(self):
        super().run()

        # click the printers tab
        self.click_machine()

        # Check if the printer is idle
        low_ink = pyautogui.locateOnScreen("images/low-ink.png", confidence=0.9)
        if low_ink:
            return False

        return True
