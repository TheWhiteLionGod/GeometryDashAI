import pyautogui

while True:
    x, y = pyautogui.position()
    print(f"Mouse position: X={x}, Y={y}")