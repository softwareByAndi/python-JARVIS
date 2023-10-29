"""
This file is for streaming audio conversion and playback. 
    - Current cost of eleven labs TTS is $0.30 per 1000 characters
    - This script will convert as much as possible up until the cost limit.)
    - I've considered using cheaper TTS, but the quality of eleven labs is just so much better than the others I've tried. 
        - Next best competitor right now is playHT TTS which is $0.22 per 1000 characters, and the quality is good enough to consider, but eleven labs is much better.


A typical stream streams the bytes as they are created,
This file instead converts the text into chunks (blocks of 500-5000 characters) and converts them into audio chunks.
    - The converted audio chunk is saved to a temporary file, and the filepath is added to a list of converted files.
    - The index of the new filepath is added to a queue of audio chunks to play. 
    - This queue is limited to 4 items, and if the queue is full, the program will wait until an item is removed from the queue before adding a new item.


- The audio producer thread converts the audio and adds them to the queue. 
- The audio consumer thread will play the audio chunks in the queue, 
- And the user can control the audio playback with the arrow keys, spacebar, and number keys.


CMD LINE ARGUMENTS:
    file = the text file to read from. -- must be a .txt file
    cost_limit = the maximum amount to spend on the conversion. -- default is $3.00 (G_DEFAULT_COST_LIMIT)
    convert_until_limit = defaults to false
        - If true, the script will convert as much as possible up until the cost limit. 
        - If false, and if the total conversion will exceed the cost limit, the script will EXIT w/out bothering to prompt the user.
        - all text details and pricing estimation will still be displayed, however.
        
USER INPUTS:
    SPACE = pause/unpause
    p = pause/unpause (perhaps this should be changed to previous?)
    LEFT ARROW = rewind 10 seconds
    RIGHT ARROW = fast forward 10 seconds
    NUMBER = jump to (10*N)% of the audio file (1= 10%, 2= 20%, etc.)
    n = skip to next audio file
    w = rewind to beginning of current audio file


REWINDING:
If the user rewinds past the beginning of the current audio file, the previous audio file will be played, starting at 10 seconds till the end of that file (attempting to behave as if both audio files are actually just one file). 
    - The current queue item will not be popped until the audio at that index has either playing, or been skipped. 
    - So listening to any number of previous audio files will not cause the queue to be emptied, 
    - And audio conversions will not continue until the user is caught up to the current queue item and eats it from the queue 
        - (either by listening to it, or skipping it.)


BUGS
    merging audio chunks will only happen if the program finishes all chunks successfully.
        - I would like to change this to merge upon a graceful exit, but the program sometimes doesn't exit gracefully....
        - Something about not getting a lock on a thread or something...
        - For now, I'll have to make another script to merge all audio files in a given folder.
        
    there seems to be a bug where the system will crash if the terminal is resized... not sure why. 
        - I think it has something to do with the curses library, but I'm not sure. 
        - I think it's because the curses library is not thread safe, and the audio thread is trying to write to the terminal while the terminal is being resized... I'll have to look into it later

    there might also be a little bug with the current audio position not displaying the correct time. 
        - This is because pygame.mixer.music.get_pos() returns total elapsed play time, not the current position in the current audio file; 
        - So I'm using a time offset to keep track of the current position in the current audio file, and I think the logic is a little off. I'll have to look into it later.
"""

import os
import re
import threading
import queue
import curses
import pygame
import argparse
import sys
sys.path.append('../lib')
from time import sleep
from mutagen.mp3 import MP3
from datetime import datetime
import eleven_labs_wrapper as el
import merge_audio as ma


G_MAX_AUDIO_QUEUE_SIZE = 4
G_SLEEP_INTERVAL = 0.1 # sleep this many seconds between input checks
G_HARD_CHARACTER_LIMIT = 5000
G_PRICE_PER_1K_CHARACTERS = 0.3
G_PRICE_PER_CHARACTER = G_PRICE_PER_1K_CHARACTERS / 1000
# FIXME : for testing
# G_DEFAULT_COST_LIMIT = 3.00 # $3.00
G_DEFAULT_COST_LIMIT = .30 # $0.30

g_arg_filepath = ""
g_arg_filename = ""
g_chunks_to_convert = [] # list of text chunks to convert
g_temp_audio_filepaths = [] # list of audio chunk filepaths -- used to navigate audio chunk files when playing audio
g_audio_queue = queue.Queue() # index of temp audio filepaths to play
g_user_actions = queue.Queue() # character inputs from user
g_cost_limit = G_DEFAULT_COST_LIMIT
g_shutdown = False
g_header_message = "Press 'q' to quit."
g_timestamp_str = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
g_space = " " * 50

print(f"Custom formatted timestamp: {g_timestamp_str}")




# HELPER FUNCTIONS

def seconds_to_timestring(p_seconds):
    return datetime.fromtimestamp(p_seconds).strftime("%M:%S")







# THREAD FUNCTIONS
"""
(intended to be run in its own thread)

generates audio chunks and adds them to the queue
if the queue is full (G_MAX_AUDIO_QUEUE_SIZE), the thread will wait until the queue is not full before adding a new item
"""
def audio_producer(stdscr, p_text_chunks):
    global G_MAX_AUDIO_QUEUE_SIZE, g_audio_queue, g_temp_audio_filepaths, g_timestamp_str
    
    _audio_files = []
    _temp_path = f"{g_arg_filepath}{g_arg_filename}/temp/{g_timestamp_str}"
    os.makedirs(_temp_path, exist_ok=True)
    
    for i, paragraph in enumerate(p_text_chunks):
        # Check if queue has reached size limit
        while g_audio_queue.qsize() >= G_MAX_AUDIO_QUEUE_SIZE:
            sleep(1)  # Wait for 1000 milliseconds before checking again
          
        _audio = el.text_to_speech(paragraph, verbose=False)
        
        # save chunks in case of critical error before files can be merged
        audio_chunk_filepath = f"{_temp_path}/{i}.mp3"
        text_chunk_filepath = f"{_temp_path}/{i}.txt"
        ma.export_to_mp3(_audio, audio_chunk_filepath)
        with open(text_chunk_filepath, 'w') as file:
            file.write(paragraph)

        # add audio chunk to queue        
        filepath_index = len(g_temp_audio_filepaths)
        g_temp_audio_filepaths.append(audio_chunk_filepath)
        g_audio_queue.put(filepath_index)
        _audio_files.append(_audio) # save audio object for merging later
    
    # merge and save audio files now.
    concatenated_audio = ma.merge_audio(_audio_files)
    ma.save(concatenated_audio, f"{g_arg_filepath}{g_arg_filename}.mp3")
    
    # audio generation is complete. add None to queue to signal to audio consumer to exit.
    g_audio_queue.put(None)









"""
(intended to be run in its own thread)

this will read audio files from the queue and passes it to the audio player. 
This function:
    - manages the audio player
    - controls navigation between audio files during playback
    - manages eating items from the audio queue. (or not eating them) 
"""
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
            title = f"playing audio file {_current_audio_index + 1} of {len(g_temp_audio_filepaths)}..."
            command = audio_player(stdscr, filename, title, _audio_end_offset)
            _audio_end_offset = 0
            if command == "previous track":
                _current_audio_index = max(0, _current_audio_index - 1)
                _audio_end_offset = 10 * 1000 # 10 seconds
            else: # next track
                _current_audio_index += 1
                
        g_audio_queue.task_done()

    stdscr.addstr(1, 0, "exiting audio consumer thread...")
    g_shutdown = True







"""
(intended to be managed by the audio_consumer thread.)
(Not intended to be run in its own thread unless there's only one audio file to play)

this function will play an audio file and return when the audio file is done playing.
this function will also print the current audio position, and listen for user input.

PARAMS:
    stdscr: the curses screen object
    p_filename: the filepath of the audio file to play
    p_title: the title of the audio consumer
    p_end_offset_ms: the number of milliseconds to rewind from the end of the audio file. 
        - Intended to simulate as if the current audio file and the previous audio file are actually just one audio file.
        - This is used when rewinding past the beginning of one audio file and wishing to play the previous audio file. 
        - This will be set by the audio_consumer thread when the user rewinds past the beginning of the current audio file.

RETURN VALUES:
    "next track": go to next track (since this is default behavior, it's currently ignored by audio_consumer thread, but I return it anyway for clarity)
    "previous track": go to previous track (audio consumer will read this and set the end offset to start playing the previous track near the end of the audio file)
    None: audio finished playing normally
    

reads user input from the g_user_actions queue -- (accepts user input every G_SLEEP_INTERVAL seconds -- currently 0.1 seconds)
USER INPUTS:
    q = quit (read in the input listener thread. it updates g_shutdown, which is read by the audio consumer thread)
    p = pause/unpause (perhaps this should be changed to previous?)
    SPACE = pause/unpause
    LEFT ARROW = rewind 10 seconds
    RIGHT ARROW = fast forward 10 seconds
    NUMBER = jump to (10*N)% of the audio file (1= 10%, 2= 20%, etc.)
    n = skip to next audio file
    w = rewind to beginning of current audio file   
"""
def audio_player(stdscr, p_filename, p_title="", p_end_offset_ms=0):
    global g_user_actions, g_shutdown, g_header_message, g_space, G_SLEEP_INTERVAL
    _JUMP_AMOUNT = 10
    _CLEAR_INTERVAL = 1 / G_SLEEP_INTERVAL
    _interval_index = 0
    
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.music.load(p_filename)
    pygame.mixer.music.play()

    audio = MP3(p_filename)
    _total_length_ms = audio.info.length * 1000
    _time_offset_ms = 0
    _file_contents = ""
    
    with open(p_filename.replace('.mp3', '.txt'), 'r') as file:
        _file_contents = file.read()

    _status = {
        "playing": True,
        "current position": 0,
        "audio length    ": seconds_to_timestring(_total_length_ms/1000),
        "info": "",
    }
    
    # for rewinding past the beginning of the following audio file
    if p_end_offset_ms > 0:
        new_pos_ms = max(0, _total_length_ms - p_end_offset_ms)
        new_pos_s = new_pos_ms / 1000
        elapsed_time_ms = pygame.mixer.music.get_pos()
        elapsed_time_str = seconds_to_timestring(elapsed_time_ms/1000)
        _time_offset_ms = elapsed_time_ms - new_pos_ms
        pygame.mixer.music.set_pos(new_pos_s)
        _status["info"] = f"starting at {seconds_to_timestring(new_pos_s)} ({p_end_offset_ms/1000} seconds) : {elapsed_time_str}"


    # MAIN LOOP
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
        line_index = 0
        stdscr.addstr(line_index, 0, p_title)
        line_index += 2
        stdscr.addstr(line_index, 0, f"{g_header_message}{g_space}")
        line_index += 1
        stdscr.addstr(line_index, 0, f"{p_filename} : {_timestamp_str}{g_space}")
        line_index += 1
        stdscr.addstr(line_index, 0, f"elapsed time : {elapsed_time_str}{g_space}")
        line_index += 1
        for key, value in _status.items():
            stdscr.addstr(4 + line_index, 0, f"    {key} : {value}{g_space}")
            line_index += 1
        line_index += 3
        stdscr.addstr(line_index, 0, f"streaming : {_file_contents}")
        line_index += 1
        
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
                _time_offset_ms = elapsed_time_ms
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
    return "next track"






"""
(intended to be run in its own thread)

this function will listen for user input and add it to the user_actions queue
q = quit
"""
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





"""
manages threads
"""
def main(stdscr):
    listener_thread = threading.Thread(target=curses_listener, args=(stdscr,))
    listener_thread.start()
    
    audio_producer_thread = threading.Thread(target=audio_producer, args=(stdscr, g_chunks_to_convert))
    audio_producer_thread.start()

    audio_consumer_thread = threading.Thread(target=audio_consumer, args=(stdscr,))
    audio_consumer_thread.start()

    audio_producer_thread.join()
    audio_consumer_thread.join()
    listener_thread.join()


"""
a helper function to extract sentences from a text file for chunking
"""
def extract_sentences(text_content):
    text = text_content.replace('\n', ' ')
    # This regular expression matches sentences terminated by '.', '!', or '?'
    sentence_pattern = r'[^.!?]*[.!?]'
    sentences = re.findall(sentence_pattern, text)
    return [sentence.strip() for sentence in sentences if sentence.strip() != ""]








"""
primary startup / initialization logic.

Will read in command arguments, read in the text file, and chunk the text file into chunks of 500-5000 characters.
Also calculates estimated cost, prints text details and prompts for user confirmation before converting the text to audio.

chunks start at 500 characters to lessen immediate delay, then increase the limit every couple chunks to simulate streaming, while still passing in as many characters as can, which improves audio context & the quality of proper inflection in the generated voice.

only the current chunk + 3 chunks ahead will be converted at any given time. this is to reduce cost if the user decides to quit early.

ARGUMENTS:
    file = the text file to read from. -- must be a .txt file
    cost_limit = the maximum amount to spend on the conversion. -- default is $3.00 (G_DEFAULT_COST_LIMIT)
    convert_until_limit = defaults to false
        - If true, the script will convert as much as possible up until the cost limit. 
        - If false, and if the total conversion will exceed the cost limit, the script will EXIT w/out bothering to prompt the user.
        - all text details and pricing estimation will still be displayed, however.
"""
if (__name__ == "__main__"):
    
    # GET CMD LINE ARGUMENTS
    parser = argparse.ArgumentParser(description="Process a filename.")
    parser.add_argument("file", type=str, help="The name of the file to process")
    parser.add_argument("--cost_limit", type=float, default=G_DEFAULT_COST_LIMIT, help="Maximum amount to spend. don't translate any more if the cost of the conversion will exceed this amount.")
    parser.add_argument("--convert_until_limit", action="store_true", help="If true, the script will convert as much as possible up until the cost limit. If false, the script will not execute if the total conversion will exceed the cost limit.")

    args = parser.parse_args()
    g_cost_limit = args.cost_limit
    
    if (args.file == None):
        print("No filename provided.")
        exit(1)
    if (args.file.split('.')[-1] != 'txt'):
        print("File must be a .txt file.")
        exit(1)
        
    filepath_parts = args.file.split('/')[:-1]
    filepath_string = '/'.join(filepath_parts)
    g_arg_filepath = f"./{filepath_string}/" # note the postfixed /
    g_arg_filename = args.file.split('/')[-1].replace('.txt', '')
    
    print(f"filepath: {g_arg_filepath}")
    print(f"filename: {g_arg_filename}")

    # READ FILE CONTENTS
    with open(f"{g_arg_filepath}{g_arg_filename}.txt", 'r') as file:
        _text_content = file.read()
    
    _text_content = "\n\n".join(extract_sentences(_text_content))
    
    with open('test.txt', 'w') as file:
        file.write(_text_content)
    
    # PRINT FILE DETAILS AND ESTIMATED COST
    print('')
    print(f"Number of characters: {len(_text_content)}")
    print(f"Estimated cost: ${round(len(_text_content) * G_PRICE_PER_CHARACTER, 2)}")
    print('')
    print(f"Cost limit: ${round(g_cost_limit, 2)}")
    print(f"Convert until limit: {args.convert_until_limit}")
    
    if (not args.convert_until_limit and len(_text_content) * G_PRICE_PER_CHARACTER > g_cost_limit):
        print("Conversion will exceed cost limit. Exiting.")
        exit(1)





    # CHUNK TEXT FOR STREAMING & API LIMITS

    # split the text into chunks to fit within the character limit
    # start with 500 characters to lessen immediate delay
    # then increase the limit every couple chunks to simulate streaming
    character_limit_stages = [ 
        { "index": 0, "chunk_size": 500 },
        { "index": 4, "chunk_size": 1000 },
        { "index": 7, "chunk_size": 2000 },
        { "index": 10, "chunk_size": 3000 },
        { "index": 13, "chunk_size": 4000 },
        { "index": 16, "chunk_size": G_HARD_CHARACTER_LIMIT }
    ]
    char_limit_stage_index = 0
    character_limit = character_limit_stages[char_limit_stage_index]["chunk_size"]
    char_limit_stage_index += 1

    paragraphs = [paragraph.strip() for paragraph in _text_content.split("\n\n") if paragraph.strip() != ""]
    chunks = []
    chunk = ""

    paragraph_index = 0
    while paragraph_index < len(paragraphs):
        chunk += paragraphs[paragraph_index] + "\n"
        paragraph_index += 1
        
        if char_limit_stage_index < len(character_limit_stages) \
                and len(chunks) >= character_limit_stages[char_limit_stage_index]["index"]:
            character_limit = character_limit_stages[char_limit_stage_index]["chunk_size"]
            char_limit_stage_index += 1
        
        if len(chunk) > character_limit:
            chunks.append(chunk)
            chunk = ""
                    
    if chunk != "":
        chunks.append(chunk)
        
    
    
    
    # GET LIST CHUNKS WITHIN COST LIMIT
    sum_price = 0
    for chunk in chunks:
        chunk_price = len(chunk) * G_PRICE_PER_CHARACTER
        if sum_price + chunk_price > g_cost_limit:
            break
        g_chunks_to_convert.append(chunk)
        sum_price += chunk_price
        
    g_chunks_to_convert = [chunk for chunk in g_chunks_to_convert if chunk.strip() != ""]
    
    # USER CONFIRMATION
    num_chunks = len(g_chunks_to_convert)
    print('')
    print(f"number of chunks to convert:  {num_chunks} / {len(chunks)}")
    print(f"length of first {num_chunks} chunks:    {sum([len(chunk) for chunk in g_chunks_to_convert])} / {len(_text_content)} characters")
    print(f"price of first {num_chunks} chunks:     ${sum_price}")
    
    print('')
    print(f"\na buffer of only {G_MAX_AUDIO_QUEUE_SIZE} audio chunks will be converted at any given time.")
    print(f"\nas audio plays, and chunks are removed from the queue, new chunks will be added to the queue until all chunks have been converted.")
    print(f"\neach audio chunk is saved in the temps folder upon conversion. if the program quits early, the individual mp3 files can still be found in the temps folder.")
    print(f"\nif the program finishes successfully, all chunks will be merged, and the final audio file will be saved next to the origin text file.")
    
    
    print('')
    for chunk in g_chunks_to_convert:
        print(f"{len(chunk)}")
    
    print('')
    confirmation = input("Do you want to continue? (y/n): ")
    if confirmation.lower() != 'y':
        print("Exiting program.")
        exit()
    
    
    
    curses.wrapper(main)
else:
    print("This file is intended to be run as a script, not imported as a module.")
    exit(1)
