from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class CheckIfShouldMoisturize(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Check if should moisturize", **kwargs)

    def run(self):
        super().run()

        # click the printers tab
        self.click_machine()

        pyautogui.sleep(1)

        # Check if the inject ink button is visible
        inject_ink = pyautogui.locateCenterOnScreen(
            "images/inject-ink.png", confidence=0.9
        )
        if inject_ink:
            pyautogui.click(self.transform_point_to_non_retina(inject_ink))
        else:
            return True  # No need to moisturize

        pyautogui.sleep(2)

        # Moisturizing
        # Loop until the machine is idle again and therefore finished with scanning
        checks = 0
        while True:
            pyautogui.sleep(1)
            online = pyautogui.locateOnScreen(
                "images/inject-ink-complete.png", confidence=0.9
            )
            if online:
                break
            checks += 1
            if checks > 300:
                return False

        # Confirm the completion dialog
        confirm = pyautogui.locateCenterOnScreen("images/ok.png", confidence=0.9)
        if confirm:
            pyautogui.click(self.transform_point_to_non_retina(confirm))
        else:
            return False

        pyautogui.sleep(2)

        return True
