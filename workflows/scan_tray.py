from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class ScanTray(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Scan Tray", **kwargs)

    def run(self, canvas_index=0):
        super().run()

        self.click_canvas_index(index=canvas_index)

        center = pyautogui.locateCenterOnScreen("images/snapshot.png", confidence=0.9)
        if not center:
            return False

        print(self.transform_point_to_non_retina(center))
        pyautogui.click(self.transform_point_to_non_retina(center))

        # Give it a little while to start
        pyautogui.sleep(2)

        # Open the machine tab
        self.click_machine()

        # Loop until the machine is idle again and therefore finished with scanning
        while True:
            pyautogui.sleep(1)
            online = pyautogui.locateOnScreen("images/idle.png", confidence=0.9)
            if online:
                break

        return True
