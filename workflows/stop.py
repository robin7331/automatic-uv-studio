from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class Stop(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Stop Workflow", **kwargs)

    def run(self):
        super().run()

        # click the machine icon to reset the UI
        self.click_machine()

        # find the stop button
        center = pyautogui.locateCenterOnScreen(
            self.get_image_path("stop.png"), confidence=0.9
        )
        if not center:
            return False

        pyautogui.click(self.transform_point_to_non_retina(center))

        pyautogui.sleep(2)

        # Find the confirm button
        center = pyautogui.locateCenterOnScreen(
            self.get_image_path("confirm.png"), confidence=0.9
        )
        if not center:
            return False

        pyautogui.click(self.transform_point_to_non_retina(center))

        pyautogui.sleep(2)

        # wait until it is finished with printing
        checks = 0
        while True:
            pyautogui.sleep(1)
            if not pyautogui.locateOnScreen(
                self.get_image_path("printing.png"), confidence=0.9
            ):
                break

            checks += 1
            if checks > 10:
                return False

        pyautogui.sleep(2)

        # When stopping mid print (not just mid scanning) there will be a final dialog.
        center = pyautogui.locateCenterOnScreen(
            self.get_image_path("stop-finish.png"), confidence=0.9
        )
        if center:
            pyautogui.click(self.transform_point_to_non_retina(center))

        pyautogui.sleep(2)

        return True
