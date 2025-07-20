import pynput.keyboard as keyboard
import pynput.mouse as mouse
import numpy as np
import pyautogui
import mss
import time
import win32gui
import win32con
import torch
import multiprocessing as mp

# Keybinds - Use integers for better performance
IDLE = torch.tensor([0])
JUMP = torch.tensor([1])

class GeometryDash:
    def __init__(self, hwnd, rect):
        # Window Setup
        self.hwnd = hwnd
        self.x, self.y = rect[0] if rect[0] > 0 else 0, rect[1]
        self.width = rect[2] - rect[0]
        self.height = rect[3] - rect[1]
        
        # Cache monitor configuration
        self.monitor = {
            "top": self.y,
            "left": self.x,
            "width": self.width,
            "height": self.height
        }

        self.keyboard = keyboard.Controller()
        self.mouse = mouse.Controller()

        self.global_timer = 0
        self.local_timer = 0
        
        # Performance optimizations
        self.sct = mss.mss()  # Reuse MSS instance

        win32gui.SetWindowText(self.hwnd, mp.current_process().name)

    def start_game(self):
        """Start game with optimized menu detection"""
        in_menu = self.in_menu()
        if not in_menu: return
        
        self.mouse.position = (in_menu.left + in_menu.width // 2, in_menu.top + in_menu.height // 2)
        time.sleep(0.1) 
        
        self.mouse.click(mouse.Button.left)
        time.sleep(0.1)  # Reduced delay for faster response
        
        self.reset_inputs()
        self.reset_timer()

    def get_current_frame(self):
        """Optimized frame capture using cached MSS instance"""
        try:
            screenshot = self.sct.grab(self.monitor)
            return np.array(screenshot)  # Convert to numpy array directly
        except Exception as e:
            print(f"[{mp.current_process().name}] Screenshot error: {e}")
            return None

    def in_menu(self) -> bool:
        """Optimized menu detection with caching"""
        try:
            # Reduced confidence for faster detection
            result = pyautogui.locateOnScreen(
                image='resources/start_game.png', 
                region=(self.x, self.y, self.width, self.height), 
                grayscale=False,  # Grayscale for faster processing
                confidence=0.3  # Lower confidence for speed
            )
            return result
        
        except pyautogui.ImageNotFoundException:
            return False
        except Exception as e:
            print(f"[{mp.current_process().name}] Menu detection error: {e}")
            return False

    def set_focus(self):
        """Optimized window focus with cooldown"""
        try:
            # Check if window is already focused
            if win32gui.GetForegroundWindow() == self.hwnd: 
                win32gui.MoveWindow(self.hwnd, self.x, self.y, self.width, self.height, True)
                return True
            
            # Optimized focus sequence
            self.keyboard.press(keyboard.Key.alt)
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.hwnd)
            
            win32gui.MoveWindow(self.hwnd, self.x, self.y, self.width, self.height, True)
            return True
            
        except Exception as e:
            print(f"[{mp.current_process().name}] Focus error for window {self.hwnd}: {e}")
            return False

    def press_jump(self):
        """Presses the jump key."""
        self.keyboard.press(keyboard.Key.space)

    def release_jump(self):
        """Releases the jump key."""
        self.keyboard.release(keyboard.Key.space)

    def reset_inputs(self):
        """Reset all inputs - optimized"""
        try:
            self.keyboard.release(keyboard.Key.space)
            self.keyboard.release(keyboard.Key.ctrl)
            self.keyboard.release(keyboard.Key.alt)
        except:
            pass  # Ignore release errors

    def reset_timer(self):
        """Reset timers using monotonic time"""
        current_time = time.monotonic()
        self.global_timer = current_time
        self.local_timer = current_time

    def read_input(self, action):
        """Optimized input reading with tensor-free operations"""
        current_time = time.monotonic()
        
        # Calculate reward and game state
        reward = 0
        done = self.in_menu() is not False
        score = int(current_time - self.global_timer)
        # Penalize dying
        if not done: # If the game is still ongoing
            # Process action
            if action == JUMP:
                self.press_jump()
            
            elif action == IDLE:
                self.release_jump()

            else:
                reward -= 0.1 # Small penalty for non-idle actions to encourage efficiency

            # Time-based survival reward
            if current_time - self.local_timer >= 1.0:
                self.local_timer = current_time
                reward += 1.0 # Reward for surviving each second
        else:
            reward = -10.0 # Large negative reward for dying

        # Removed self.reset_inputs() from here as it's handled by the agent at game start/end.
        return reward, done, score

    def __del__(self):
        """Cleanup MSS instance"""
        try:
            if hasattr(self, 'sct'):
                self.sct.close()
            if hasattr(self, 'hwnd'):
                win32gui.SetWindowText(self.hwnd, "Geometry Dash")
        except:
            pass

if __name__ == '__main__':
    # Simple test with optimized parameters
    import win32gui
    
    def find_window(title):
        result = []
        def enum_handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == title:
                result.append(hwnd)
        win32gui.EnumWindows(enum_handler, None)
        return result[0] if result else None
    
    hwnd = find_window("Geometry Dash")
    if not hwnd:
        print(f"[{mp.current_process().name}] Geometry Dash window not found")
        exit()
    
    rect = win32gui.GetWindowRect(hwnd)
    game = GeometryDash(hwnd, rect)
    
    game.reset_inputs()
    game.reset_timer()
    game.start_game()

    for _ in range(2):
        while not game.in_menu():
            if not game.set_focus():
                break
            reward, done, score = game.read_input(JUMP)
            time.sleep(0.1)  # Reduced delay

        game.reset_inputs()
        game.reset_timer()
        game.start_game()
