from time import sleep
import threading
import queue
import curses
import pygame
from mutagen.mp3 import MP3
from datetime import datetime


shutdown = False
user_actions = queue.Queue()
header_message = "Press 'q' to quit."

def seconds_to_timestring(seconds):
    return datetime.fromtimestamp(seconds).strftime("%M:%S")

def audio_player(stdscr, filename):
    global user_actions, shutdown
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()

    audio = MP3(filename)
    total_length_ms = audio.info.length * 1000
    time_offset_ms = 0

    status = {
        "playing": True,
        "current position": 0,
        "audio length    ": seconds_to_timestring(total_length_ms/1000),
        "info": "",
    }
    
    space = " " * 50
    clear_interval = 10
    interval_index = 0
    
    
    while not shutdown:
        # exit thread when audio is done playing
        if not pygame.mixer.music.get_busy():
            if status["playing"]: # not paused
                break
        
        # another option is to use stdscr.clrtoeol(0) for individual lines
        if interval_index >= clear_interval:
            stdscr.clear()
            interval_index = 0
        else:
            interval_index += 1
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        elapsed_time_ms = pygame.mixer.music.get_pos()
        elapsed_time_str = seconds_to_timestring(elapsed_time_ms/1000)
        real_pos_ms = elapsed_time_ms - time_offset_ms
        real_pos_str = seconds_to_timestring(real_pos_ms/1000)
        
        status["current position"] = real_pos_str
        
        # PRINT
        stdscr.addstr(0, 0, header_message)
        stdscr.addstr(1, 0, f"{filename} : {timestamp_str}{space}")
        stdscr.addstr(2, 0, f"elapsed time : {elapsed_time_str}{space}")
        for index, [key, value] in enumerate(status.items()):
            stdscr.addstr(4 + index, 0, f"    {key} : {value}{space}")
        
        try:
            action = user_actions.get_nowait()
        except queue.Empty:
            action = None

        if action is not None:
            if action == 'p' or action == ' ':
                if status["playing"]:
                    pygame.mixer.music.pause()
                else:
                    pygame.mixer.music.unpause()
                status["playing"] = not status["playing"]
                
            elif action == 'w':
                elapsed_time_ms = pygame.mixer.music.get_pos()
                time_offset_ms += elapsed_time_ms
                pygame.mixer.music.rewind()
                
            elif "ARROW" in action:
                elapsed_time_ms = pygame.mixer.music.get_pos()
                elapsed_time_s = elapsed_time_ms / 1000
                real_pos_ms = elapsed_time_ms - time_offset_ms
                real_pos_s = real_pos_ms / 1000
                
                JUMP_AMOUNT = 10
                if action == "LEFT ARROW":
                    seconds_to_shift = -JUMP_AMOUNT
                elif action == "RIGHT ARROW":
                    seconds_to_shift = JUMP_AMOUNT
                else:
                    seconds_to_shift = 0
                if seconds_to_shift != 0:
                    time_offset_ms -= seconds_to_shift * 1000
                    new_pos_s = max(0, real_pos_s + seconds_to_shift)
                    
                    time_string = seconds_to_timestring(new_pos_s)
                    status["info"] = f"jumping to {time_string} ({seconds_to_shift} seconds)"
                    # status["info"] = f"rewinding: {elapsed_time_s} : {real_pos_s} : {seconds_to_shift} : {new_pos_s}"
                    pygame.mixer.music.set_pos(new_pos_s)
            
            elif action.isdigit():
                new_pos_ms = total_length_ms * (int(action) / 10)
                elapsed_time_ms = pygame.mixer.music.get_pos()
                time_offset_ms = elapsed_time_ms - new_pos_ms
                new_pos_s = new_pos_ms / 1000
                time_string = seconds_to_timestring(new_pos_s)
                status["info"] = f"jumping to {time_string}"
                pygame.mixer.music.set_pos(new_pos_s)
                    
            user_actions.task_done()

        sleep(0.1)

    # EXIT
    stdscr.clear()
    stdscr.addstr(0, 0, "exiting audio thread...")
    shutdown = True

def curses_listener(stdscr):
    global shutdown
    global user_actions

    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)

    while not shutdown:
        c = stdscr.getch()
        stdscr.refresh()
        # char_c = chr(c)
        
        if c == ord('q'):
            print("Quitting.")
            shutdown = True
            break
        elif c == curses.KEY_LEFT:
            user_actions.put("LEFT ARROW")
        elif c == curses.KEY_RIGHT:
            user_actions.put("RIGHT ARROW")
        elif c != -1:  # -1 means no key was pressed
            user_actions.put(chr(c))

def main(stdscr):
    listener_thread = threading.Thread(target=curses_listener, args=(stdscr,))
    listener_thread.start()

    audio_thread = threading.Thread(target=audio_player, args=(stdscr, "../audiobook_temps/release_that_witch/ch879.mp3"))
    audio_thread.start()

    audio_thread.join()
    listener_thread.join()

if (__name__ == "__main__"):
    curses.wrapper(main)
else:
    print("This file is intended to be run as a script, not imported as a module.")
    exit(1)
