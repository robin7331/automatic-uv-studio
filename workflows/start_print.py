from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class StartPrint(Workflow):
    def __init__(self, *args, publish_control_message=None, **kwargs):
        super().__init__(*args, name="Start Print", **kwargs)
        self.publish_control_message = publish_control_message

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
        checks = 0
        while True:
            pyautogui.sleep(1)
            ready = pyautogui.locateOnScreen(
                "images/ready_to_start.png", confidence=0.9
            )
            if ready:
                break
            checks += 1
            if checks > 10:
                return False

        pyautogui.sleep(2)
        # Send MQTT message to press the physical start button
        self.publish_control_message("press_start_button")
        pyautogui.sleep(2)

        # Open the machine tab
        self.click_machine()

        # wait until
        checks = 0
        while True:
            pyautogui.sleep(1)
            online = pyautogui.locateOnScreen("images/printing.png", confidence=0.9)
            if online:
                break
            checks += 1
            if checks > 10:
                return False

        pyautogui.sleep(4)

        # Loop until the print is complete
        checks = 0
        while True:
            pyautogui.sleep(1)
            complete = pyautogui.locateOnScreen(
                "images/print_complete.png", confidence=0.9
            )
            if complete:
                break
            checks += 1
            if checks > 600:
                return False

        center = pyautogui.locateCenterOnScreen("images/finish.png", confidence=0.9)
        if not center:
            return False

        print(self.transform_point_to_non_retina(center))
        pyautogui.click(self.transform_point_to_non_retina(center))

        return True
