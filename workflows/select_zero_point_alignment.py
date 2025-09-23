from .workflow import Workflow
import pyautogui
import pywinctl as pwc


class SelectZeroPointAlignment(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name="Select Zero Point Alignment", **kwargs)

    def run(self, canvas_index=0):
        super().run()

        self.click_canvas_index(index=canvas_index)

        y_offset = 413

        # If snapshot is selected the offset is larger
        center = pyautogui.locateCenterOnScreen(
            self.get_image_path("snapshot.png"), confidence=0.9
        )
        if center:
            print("Snapshot detected, adjusting offset")
            y_offset = 458
        else:
            print("No snapshot detected, using default offset")

        # select the zero point alignment option
        self.click_at(36, y_offset, relative_to_right_window_side=True)

        pyautogui.sleep(2)

        # Quick check if the selection was successful
        center = pyautogui.locateCenterOnScreen(
            self.get_image_path("recalibrate-zero-point.png"), confidence=0.9
        )
        if not center:
            return False

        return True
