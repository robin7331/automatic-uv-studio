import pyautogui
import os


class Workflow:
    def __init__(
        self,
        name=None,
        window_rect=None,
        is_retina=True,
        image_path="images",
        logger=None,
    ):
        self.name = name
        self.is_retina = is_retina
        self.window_rect = window_rect
        self.image_path = image_path
        self.logger = logger

    def get_image_path(self, image_name):
        """Get the full path to an image based on retina setting"""
        return os.path.join(self.image_path, image_name)

    def transform_point_to_non_retina(self, point):
        if self.is_retina:
            return (point.x / 2, point.y / 2)
        return (point.x, point.y)

    def click_at(self, x, y, sleep=True, relative_to_right_window_side=False):
        if relative_to_right_window_side:
            pyautogui.click(self.window_rect.right - x, self.window_rect.top + y)
        else:
            pyautogui.click(self.window_rect.left + x, self.window_rect.top + y)
        if sleep:
            pyautogui.sleep(2)

    def click_home(self):
        self.click_at(45, 45)

    def click_machine(self):
        self.click_at(130, 45)

    def click_canvas_index(self, index=0, canvas_button_width=128):
        offset = (
            168  # from the left edge of the window until the first canvas tab begins
        )

        # click the canvas tab
        self.click_at(
            offset + (index * canvas_button_width) + (canvas_button_width / 2), 45
        )

    def run(self):
        print(f"Running workflow: {self.name}")
