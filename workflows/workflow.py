import pyautogui


class Workflow:
    def __init__(self, name=None, window_rect=None, is_retina=True):
        self.name = name
        self.is_retina = is_retina
        self.window_rect = window_rect

    def transform_point_to_non_retina(self, point):
        if self.is_retina:
            return (point.x / 2, point.y / 2)
        return (point.x, point.y)

    def click_at(self, x, y, sleep=True):
        pyautogui.click(self.window_rect.left + x, self.window_rect.top + y)
        if sleep:
            pyautogui.sleep(1)

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
