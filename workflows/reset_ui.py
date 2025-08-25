from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class ResetUIWorkflow(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Reset UI Workflow", **kwargs)

    def run(self):
        super().run()

        # click the home icon to reset the UI
        self.click_home()

        # check if we can find the clean-bar.png screenshot so we are sure that the UI is where we want it to be
        # meaning the two files are open and not active.
        clean_bar = pyautogui.locateOnScreen("images/clean-bar.png", confidence=0.8)
        if not clean_bar:
            return False

        return True
