from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class StartPrint(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Start Print", **kwargs)

    def run(self, canvas_index=0):
        super().run()

        self.click_canvas_index(index=canvas_index)

        center = pyautogui.locateCenterOnScreen("images/print.png", confidence=0.9)
        if not center:
            return False

        pyautogui.click(self.transform_point_to_non_retina(center))

        # Give it a little while to start
        pyautogui.sleep(2)

        # Wait for the printer to be ready
        while True:
            pyautogui.sleep(1)
            ready = pyautogui.locateOnScreen(
                "images/ready_to_start.png", confidence=0.9
            )
            if ready:
                break

        print("Printer ready")

        # Here you would now hit the start button on the actual printer itself
        pyautogui.sleep(10)

        # Open the machine tab
        self.click_machine()

        # wait until
        while True:
            pyautogui.sleep(1)
            online = pyautogui.locateOnScreen("images/printing.png", confidence=0.9)
            if online:
                break

        print("Printer is printing!")

        pyautogui.sleep(4)

        # Loop until the print is complete
        while True:
            pyautogui.sleep(1)
            complete = pyautogui.locateOnScreen(
                "images/print_complete.png", confidence=0.9
            )
            if complete:
                break

        print("Print complete!")

        center = pyautogui.locateCenterOnScreen("images/finish.png", confidence=0.9)
        if not center:
            return False

        print(self.transform_point_to_non_retina(center))
        pyautogui.click(self.transform_point_to_non_retina(center))

        return True
