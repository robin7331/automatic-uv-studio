import pyautogui
import pywinctl as pwc
from workflows.reset_ui import ResetUIWorkflow
from workflows.check_if_online import CheckIfOnline
from workflows.check_if_printer_idle import CheckIfIdle
from workflows.scan_tray import ScanTray
from workflows.workflow import Workflow
from workflows.start_print import StartPrint
import pyscreeze

pyscreeze.USE_IMAGE_NOT_FOUND_EXCEPTION = False


def main():
    screenWidth, screenHeight = pyautogui.size()

    # activate the window and raise an error if not found
    window = pwc.getWindowsWithTitle("eufy", pwc.Re.CONTAINS)
    if not window and not window[0]:
        raise ValueError("Window not found")
    window[0].activate(wait=True)

    # get the window size and position
    window_rect = window[0].rect

    # reset the screen
    reset_ui = ResetUIWorkflow(window_rect=window_rect)
    if not reset_ui.run():
        print("Could not reset the UI")
        return

    # check if printer online
    check_if_online = CheckIfOnline(window_rect=window_rect)
    if not check_if_online.run():
        print("Printer not online")
        return

    # Make sure the printer is idle
    check_if_idle = CheckIfIdle(window_rect=window_rect)
    if not check_if_idle.run():
        print("Printer not idle")
        return

    # Scan the tray
    scan_tray = ScanTray(window_rect=window_rect)
    if not scan_tray.run(canvas_index=0):
        print("Failed to scan tray")
        return

    # Print
    start_print = StartPrint(window_rect=window_rect)
    if not start_print.run(canvas_index=0):
        print("Failed to print")
        return

    print("Finished!")


if __name__ == "__main__":
    main()
