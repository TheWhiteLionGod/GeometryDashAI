from pynput import keyboard as pynput_keyboard
from game import GeometryDash, JUMP
from agent import Player, BATCH_SIZE
import multiprocessing as mp
import win32gui
import time

# Settings
WINDOW_NAME = "Geometry Dash"
JUMP_INTERVAL = 0.5

def find_all_windows(title):
    """Find all windows with the specified title - optimized with early return"""
    result = []
    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd)
            if window_text == title:
                result.append(hwnd)
    win32gui.EnumWindows(enum_handler, None)
    return result

def validate_window(hwnd):
    """Check if window handle is still valid"""
    try:
        return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
    except:
        return False

def bot_loop(hwnd, player: Player, stop_event, input_lock, shared_memory_list):
    """Optimized bot loop with better error handling and performance"""
    # try:
    rect = win32gui.GetWindowRect(hwnd)
    game = GeometryDash(hwnd, rect)
    
    player.model.load()
    player.model = player.model.to(player.device)

    record = 0
    score = 0
    while not stop_event.is_set():
        game.reset_inputs()
        game.reset_timer()
        game.start_game()
        
        while game.in_menu() is False:
            if not validate_window(hwnd):
                print(f"Window {hwnd} is no longer valid")
                break

            state_old = player.get_state(game)
            final_move = player.get_action(state_old)

            # Use input lock to prevent race conditions
            with input_lock:
                game.reset_inputs()
                if not game.set_focus(): break
                reward, done, score = game.read_input(final_move)

            state_new = player.get_state(game)
            
            # train short memory
            player.train_short_memory(state_old, final_move, reward, state_new, done)
            player.remember(state_old, final_move, reward, state_new, done)

        player.n_games += 1
        game.reset_inputs()
        
        if len(player.memory) > 0:
            for memory in player.memory:
                shared_memory_list.append(memory)
            player.memory.clear()
        
        # Occassionally Training on Shared Memory
        if len(shared_memory_list) > BATCH_SIZE:
            print(f'[{mp.current_process().name}] Started long term training..')
            # Loading Data to Player Memory
            player.memory = list(shared_memory_list)
            del shared_memory_list[:]

            # Training the Model
            player.train_long_memory()
            player.memory.clear()
            
            # Saving Model
            player.model.save()

        if score > record: 
            record = score
            player.model.save(file_name=f"record_{record}.pth")
            print(f'[{mp.current_process().name}] Game {player.n_games} New Record {record}')

        if stop_event.is_set(): break
    print(f"[{mp.current_process().name}] Stopping bot loop for window {hwnd}")

    # except Exception as e:
    #     print(f"[{mp.current_process().name}] Error in bot loop for window {hwnd}: {e}")

def create_bot_process(hwnds: list[int], players:list[Player], stop_event, input_lock, shared_memory_list):
    bot_threads = []
    """Create a bot processes for each window handle"""
    for i, hwnd in enumerate(hwnds):
        try:
            player = players[i]
            
            proc = mp.Process(
                target=bot_loop, 
                args=(hwnd, player, stop_event, input_lock, shared_memory_list),
                daemon=True,
                name=f"Bot-{i}"
            )
            
            proc.start()
            bot_threads.append(proc)
            time.sleep(JUMP_INTERVAL/len(hwnds)) # Offsetting start times to reduce input competition

        except Exception as e:
            print(f"[{mp.current_process().name}] Failed to start bot for window {hwnd}: {e}")
    return bot_threads

def main():
    hwnds = find_all_windows(WINDOW_NAME)
    if not hwnds:
        print(f"[{mp.current_process().name}] No Geometry Dash windows found.")
        return

    print(f"[{mp.current_process().name}] Found {len(hwnds)} Geometry Dash windows.")

    # Initialize players and games
    stop_event = mp.Event()
    input_lock = mp.Lock()
    manager = mp.Manager()
    shared_memory_list = manager.list()
    
    players = [Player() for _ in hwnds]
    bot_threads = create_bot_process(hwnds, players, stop_event, input_lock, shared_memory_list)

    if not bot_threads:
        print(f"[{mp.current_process().name}] No bot threads started successfully.")
        return

    print(f"[{mp.current_process().name}] Bot started. Press ESC to stop.")

    def on_press(key):
        if key == pynput_keyboard.Key.esc:
            print(f"[{mp.current_process().name}] ESC pressed. Stopping...")
            stop_event.set()
            return False

    # Use context manager for cleaner resource management
    with pynput_keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    for proc in bot_threads:
        proc.join()

    print(f"[{mp.current_process().name}] Clean shutdown complete.")

if __name__ == "__main__":
    main()