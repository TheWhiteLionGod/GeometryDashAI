import time
import threading
import win32gui
import win32api
import win32process
import win32con
from pynput import keyboard as pynput_keyboard
import pynput.keyboard as keyboard_controller

# Settings
WINDOW_NAME = "Geometry Dash"

attached_threads = set()
input_lock = threading.Lock()

def find_all_windows(title):
    result = []
    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == title:
            result.append(hwnd)
    win32gui.EnumWindows(enum_handler, None)
    return result

def attach_input(hwnd):
    current_thread = win32api.GetCurrentThreadId()
    target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

    if not target_thread or target_thread == current_thread:
        return

    if target_thread not in attached_threads:
        try:
            win32process.AttachThreadInput(current_thread, target_thread, True)
            attached_threads.add(target_thread)
        except Exception as e:
            pass

def detach_all_input():
    current_thread = win32api.GetCurrentThreadId()
    for tid in list(attached_threads):
        try:
            win32process.AttachThreadInput(current_thread, tid, False)
            attached_threads.remove(tid)
        except Exception as e:
            pass

def set_focus(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        return False

def bot_loop(hwnd, stop_event, rect):
    controller = keyboard_controller.Controller()
    x, y = rect[0], rect[1]
    width = rect[2] - rect[0]
    height = rect[3] - rect[1]

    while not stop_event.is_set():
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            break
        
        with input_lock:
            if not set_focus(hwnd):
                continue

            win32gui.MoveWindow(hwnd, x, y, width, height, True)

            try:
                controller.press(keyboard_controller.Key.space)
                time.sleep(0.1)
                controller.release(keyboard_controller.Key.space)
            except Exception as e:
                pass
            time.sleep(0.5)

def main():
    hwnds = find_all_windows(WINDOW_NAME)
    if not hwnds:
        return

    stop_event = threading.Event()
    bot_threads = []

    for hwnd in hwnds:
        # Start bot
        rect = win32gui.GetWindowRect(hwnd)
        t = threading.Thread(target=bot_loop, args=(hwnd, stop_event, rect), daemon=True)
        t.start()
        bot_threads.append(t)
        time.sleep(0.25)  # Stagger thread creation

    def on_press(key):
        if key == pynput_keyboard.Key.esc:
            stop_event.set()
            return False

    with pynput_keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    for t in bot_threads:
        t.join()

    detach_all_input()

if __name__ == "__main__":
    main()
