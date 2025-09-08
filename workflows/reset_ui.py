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

        return True
