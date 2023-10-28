import os
import sys
sys.path.append('../lib')
from datetime import datetime
import threading
import queue
import argparse
import eleven_labs_wrapper as el
import merge_audio as ma

# Initialize a thread-safe queue
audio_queue = queue.Queue()

timestamp_str = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
print(f"Custom formatted timestamp: {timestamp_str}")

def audio_producer(text_chunks, filepath, filename):
    audio_files = []
    temp_path = f"{filepath}{filename}/temp/{timestamp_str}"
    os.makedirs(temp_path, exist_ok=True)
    
    for i, paragraph in enumerate(text_chunks):
        audio = el.text_to_speech(paragraph)
        audio_queue.put(audio)
        audio_files.append(audio)
        # save chunks in case of critical error before files can be merged
        ma.export_to_mp3(audio, f"{temp_path}/{i}.mp3")
    
    # merge and save audio files now.
    concatenated_audio = ma.merge_audio(audio_files)
    ma.save(concatenated_audio, f"{filepath}{filename}.mp3")

def audio_consumer():
    while True:
        # Remove and return an item from the queue.
        audio = audio_queue.get()
        if audio is None:
            # None is a signal to exit.
            break
        el.play(audio)
        audio_queue.task_done()






if (__name__ == "__main__"):
    parser = argparse.ArgumentParser(description="Process a filename.")
    parser.add_argument("file", type=str, help="The name of the file to process")

    args = parser.parse_args()
    
    if (args.file == None):
        print("No filename provided.")
        exit(1)
    if (args.file.split('.')[-1] != 'txt'):
        print("File must be a .txt file.")
        exit(1)
    
    _filepath_parts = args.file.split('/')[:-1]
    _filepath_string = '/'.join(_filepath_parts)
    filepath = f"./{_filepath_string}/" # note postfixed /
    filename = args.file.split('/')[-1].replace('.txt', '')

    with open(f"{filepath}{filename}.txt", 'r') as file:
        text_content = file.read()

    # split the text into chunks (api limit is 5k characters)
    character_limit = 5000
    paragraphs = text_content.split("\n\n")
    chunks = []
    chunk = ""
    for paragraph in paragraphs:
        if len(chunk) + len(paragraph) > character_limit:
            chunks.append(chunk)
            chunk = ""
        if len(paragraph) > character_limit:
            for sentence in paragraph.split('.'):
                if len(chunk) + len(sentence) > character_limit:
                    chunks.append(chunk)
                    chunk = ""
                if len(sentence) > character_limit:
                    raise Exception(f"Sentence is too long to be processed by the API. current limit is {character_limit} characters.")
                chunk += sentence + "."
        else:
            chunk += paragraph + "\n\n"
    if chunk != "":
        chunks.append(chunk)

    # Start the producer thread
    producer_thread = threading.Thread(target=audio_producer, args=(chunks, filepath, filename,))
    producer_thread.start()

    # Start the consumer thread
    consumer_thread = threading.Thread(target=audio_consumer)
    consumer_thread.start()

    # Wait for the producer thread to finish adding all audio to the queue
    producer_thread.join()

    # Wait for all audio to be played
    audio_queue.join()

    # Stop the consumer thread
    audio_queue.put(None)
    consumer_thread.join()


    
else:
    print("This file is intended to be run as a script, not imported as a module.")
    exit(1)