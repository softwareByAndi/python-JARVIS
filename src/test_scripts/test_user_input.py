from time import sleep
import threading
import queue
import curses
from datetime import datetime

shutdown = False
user_actions = queue.Queue()
header_message = "Press 'q' to quit."

def logger(stdscr, name="default", interval=0.5):
    global shutdown
    global user_actions
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)

    clear_interval = max(1, 1/interval)
    interval_index = 0
    while not shutdown:
        # another option is to use stdscr.clrtoeol(0) for individual lines
        if interval_index >= clear_interval:
            stdscr.clear()
            interval_index = 0
        else:
            interval_index += 1
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        stdscr.addstr(0, 0, header_message)
        # Extra spaces to clear previous message
        stdscr.addstr(1, 0, f"I'm alive! {name} : {timestamp_str}                         ")

        # If action in queue, pop and print it
        try:
            action = user_actions.get_nowait()
        except queue.Empty:
            action = None
        if action is not None:
            # Extra spaces to clear previous message
            stdscr.addstr(2, 0, f"Received action: {action}                       ")  
            user_actions.task_done()

        stdscr.refresh()
        sleep(interval)

def curses_listener(stdscr):
    global shutdown
    global user_actions

    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)

    while not shutdown:
        c = stdscr.getch()
        stdscr.refresh()

        if c == ord('q'):
            print("Quitting.")
            shutdown = True
            break
        elif c != -1:  # -1 means no key was pressed
            user_actions.put(chr(c))

def main(stdscr):
    listener_thread = threading.Thread(target=curses_listener, args=(stdscr,))
    logger_thread = threading.Thread(target=logger, args=(stdscr, "alpha", 0.1))

    logger_thread.start()
    listener_thread.start()

    logger_thread.join()
    listener_thread.join()

if (__name__ == "__main__"):
    curses.wrapper(main)
else:
    print("This file is intended to be run as a script, not imported as a module.")
    exit(1)
