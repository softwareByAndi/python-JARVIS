import os
import threading
import queue
import curses
import pygame
import argparse
import sys
sys.path.append('../../lib')
from time import sleep
from mutagen.mp3 import MP3
from datetime import datetime


G_MAX_AUDIO_QUEUE_SIZE = 4
G_SLEEP_INTERVAL = 0.1 # sleep this many seconds between input checks
G_HARD_CHARACTER_LIMIT = 5000
G_PRICE_PER_1K_CHARACTERS = 0.3
G_PRICE_PER_CHARACTER = G_PRICE_PER_1K_CHARACTERS / 1000
# FIXME : for testing
# G_DEFAULT_COST_LIMIT = 3.00 # $3.00
G_DEFAULT_COST_LIMIT = .30 # $0.30

g_chunks_to_convert = [] # list of text chunks to convert
g_temp_audio_filepaths = [] # list of audio chunk filepaths -- used to navigate audio chunk files when playing audio
g_audio_queue = queue.Queue() # index of temp audio filepaths to play
g_user_actions = queue.Queue() # character inputs from user
g_cost_limit = G_DEFAULT_COST_LIMIT
g_shutdown = False
g_header_message = "Press 'q' to quit."
g_timestamp_str = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

print(f"Custom formatted timestamp: {g_timestamp_str}")




# HELPER FUNCTIONS

def seconds_to_timestring(p_seconds):
    return datetime.fromtimestamp(p_seconds).strftime("%M:%S")





# MAIN FUNCTIONS

def audio_consumer(stdscr):
    global g_shutdown, g_temp_audio_filepaths, g_audio_queue
    _current_audio_index = 0
    _audio_end_offset = 0
    
    while not g_shutdown:
        # Remove and return an item from the queue.
        _queue_audio_index = g_audio_queue.get()
        if _queue_audio_index is None:
            # None is a signal to exit.
            g_shutdown = True
            break
        while not g_shutdown and _current_audio_index <= _queue_audio_index:
            filename = g_temp_audio_filepaths[_current_audio_index]
            command = audio_player(stdscr, filename, _audio_end_offset)
            _audio_end_offset = 0
            if command == "previous track":
                _current_audio_index = max(0, _current_audio_index - 1)
                _audio_end_offset = 10 * 1000 # 10 seconds
            else: # next track
                _current_audio_index += 1
                
        g_audio_queue.task_done()

    stdscr.addstr(1, 0, "exiting audio consumer thread...")
    g_shutdown = True







def audio_player(stdscr, p_filename, p_end_offset_ms=0):
    global g_user_actions, g_shutdown, g_header_message, G_SLEEP_INTERVAL
    try:
        _JUMP_AMOUNT = 10
        _CLEAR_INTERVAL = 1 / G_SLEEP_INTERVAL
        _interval_index = 0
        _space = " " * 50
        
        pygame.init()
        pygame.mixer.init()
        pygame.mixer.music.load(p_filename)
        pygame.mixer.music.play()
        

        audio = MP3(p_filename)
        _total_length_ms = audio.info.length * 1000
        _time_offset_ms = 0

        _status = {
            "playing": True,
            "current position": 0,
            "audio length    ": seconds_to_timestring(_total_length_ms/1000),
            "info": "",
        }
        
        # for rewinding past the beginning of the following audio file
        if p_end_offset_ms > 0:
            new_pos_ms = _total_length_ms - p_end_offset_ms
            new_pos_s = new_pos_ms / 1000
            elapsed_time_ms = pygame.mixer.music.get_pos()
            elapsed_time_str = seconds_to_timestring(elapsed_time_ms/1000)
            _time_offset_ms = elapsed_time_ms - new_pos_ms
            pygame.mixer.music.set_pos(new_pos_s)
            _status["info"] = f"starting at {seconds_to_timestring(new_pos_s)} ({p_end_offset_ms/1000} seconds) : {elapsed_time_str}"
        
        
        
        
        
        while not g_shutdown:
            # exit thread when audio is done playing
            if not pygame.mixer.music.get_busy():
                if _status["playing"]: # not paused
                    break
            
            # another option is to use stdscr.clrtoeol(0) for individual lines
            if _interval_index >= _CLEAR_INTERVAL:
                stdscr.clear()
                _interval_index = 0
            else:
                _interval_index += 1
            _timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            elapsed_time_ms = pygame.mixer.music.get_pos()
            elapsed_time_str = seconds_to_timestring(elapsed_time_ms/1000)
            real_pos_ms = elapsed_time_ms - _time_offset_ms
            real_pos_str = seconds_to_timestring(real_pos_ms/1000)
            
            _status["current position"] = real_pos_str
            
            # PRINT
            stdscr.addstr(0, 0, g_header_message)
            stdscr.addstr(1, 0, f"{p_filename} : {_timestamp_str}{_space}")
            stdscr.addstr(2, 0, f"elapsed time : {elapsed_time_str}{_space}")
            for index, [key, value] in enumerate(_status.items()):
                stdscr.addstr(4 + index, 0, f"    {key} : {value}{_space}")
            
            try:
                action = g_user_actions.get_nowait()
            except queue.Empty:
                action = None

            if action is not None:
                if action == 'p' or action == ' ':
                    if _status["playing"]:
                        pygame.mixer.music.pause()
                    else:
                        pygame.mixer.music.unpause()
                    _status["playing"] = not _status["playing"]
                    
                elif action == 'w':
                    elapsed_time_ms = pygame.mixer.music.get_pos()
                    _time_offset_ms += elapsed_time_ms
                    pygame.mixer.music.rewind()
                    
                elif action == 'n':
                    pygame.mixer.music.stop()
                    return "next track"
                    
                elif "ARROW" in action:
                    elapsed_time_ms = pygame.mixer.music.get_pos()
                    real_pos_ms = elapsed_time_ms - _time_offset_ms
                    real_pos_s = real_pos_ms / 1000
                    
                    if action == "LEFT ARROW":
                        seconds_to_shift = -_JUMP_AMOUNT
                    elif action == "RIGHT ARROW":
                        seconds_to_shift = _JUMP_AMOUNT
                    else:
                        seconds_to_shift = 0
                    if seconds_to_shift != 0:
                        _time_offset_ms -= seconds_to_shift * 1000
                        new_pos_s = real_pos_s + seconds_to_shift
                        
                        # exit audio file if we try to jump before the beginning or after the end
                        if new_pos_s < 0:
                            pygame.mixer.music.stop()
                            return "previous track"
                        elif new_pos_s > _total_length_ms / 1000:
                            pygame.mixer.music.stop()
                            return "next track"
                        
                        time_string = seconds_to_timestring(new_pos_s)
                        _status["info"] = f"jumping to {time_string} ({seconds_to_shift} seconds)"
                        pygame.mixer.music.set_pos(new_pos_s)
                
                elif action.isdigit():
                    new_pos_ms = _total_length_ms * (int(action) / 10)
                    elapsed_time_ms = pygame.mixer.music.get_pos()
                    _time_offset_ms = elapsed_time_ms - new_pos_ms
                    new_pos_s = new_pos_ms / 1000
                    time_string = seconds_to_timestring(new_pos_s)
                    _status["info"] = f"jumping to {time_string}"
                    pygame.mixer.music.set_pos(new_pos_s)
                        
                g_user_actions.task_done()

            sleep(G_SLEEP_INTERVAL)

        # EXIT
        stdscr.clear()
        stdscr.addstr(0, 0, "exiting audio player...")
    except:
        pass
    finally:
        try:
            pygame.mixer.music.stop()
        except:
            pass
        try:
            pygame.mixer.quit()
        except:
            pass
        
        return "next track"







def curses_listener(stdscr):
    global g_shutdown
    global g_user_actions

    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)

    while not g_shutdown:
        c = stdscr.getch()
        stdscr.refresh()
        # char_c = chr(c)
        
        if c == ord('q'):
            print("Quitting.")
            g_shutdown = True
            break
        elif c == curses.KEY_LEFT:
            g_user_actions.put("LEFT ARROW")
        elif c == curses.KEY_RIGHT:
            g_user_actions.put("RIGHT ARROW")
        elif c != -1:  # -1 means no key was pressed
            g_user_actions.put(chr(c))
            
        sleep(G_SLEEP_INTERVAL)






def main(stdscr):
    listener_thread = threading.Thread(target=curses_listener, args=(stdscr,))
    listener_thread.start()
    
    audio_consumer_thread = threading.Thread(target=audio_consumer, args=(stdscr,))
    audio_consumer_thread.start()

    audio_consumer_thread.join()
    listener_thread.join()


def transform_digits(filename):
    extension = filename.split('.')[-1]
    name = filename.split('.')[0]
    if name.isdigit():
        name = name.zfill(4)
    return name + '.' + extension

def get_all_files_in_folder(directory):
    unsorted_filenames = [
        f
        for f 
        in os.listdir(directory) 
            if ".mp3" in f and os.path.isfile(os.path.join(directory, f))
    ]
    sorted_filenames = sorted(unsorted_filenames, key=lambda name: int(name.split(".")[0]))
    return sorted_filenames


    



if (__name__ == "__main__"):
    
    # GET CMD LINE ARGUMENTS
    parser = argparse.ArgumentParser(description="Process a filename.")
    parser.add_argument("folder", type=str, help="The name of the file to process")

    args = parser.parse_args()
    
    if (args.folder == None):
        print("No folder provided.")
        exit(1)
        
    filepath_parts = [f for f in args.folder.split('/') if f != '' or f != '.']
    filepath_string = '/'.join(filepath_parts)
    g_arg_filepath = f"./{filepath_string}/".replace('//', '/') # note the postfixed /
    
    print(f"filepath: {g_arg_filepath}")
    
    filenames = get_all_files_in_folder(g_arg_filepath)
    for index, filename in enumerate(filenames):
        print('    ', index, ':', filename)
        g_temp_audio_filepaths.append(f"{g_arg_filepath}{filename}")
        g_audio_queue.put(index)
    g_audio_queue.put(None)
    
    print('')
    confirmation = input("play audio files?: ")
    if confirmation.lower() != 'y':
        print("Exiting program.")
        exit()
    
    curses.wrapper(main)
else:
    print("This file is intended to be run as a script, not imported as a module.")
    exit(1)
