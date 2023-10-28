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

def audio_producer(text_chunks, filename):
    audio_files = []
    temp_path = f"./audiobook_temps/{filename}/{timestamp_str}"
    os.makedirs(temp_path, exist_ok=True)
    
    for i, paragraph in enumerate(text_chunks):
        audio = el.text_to_speech(paragraph)
        audio_queue.put(audio)
        audio_files.append(audio)
        ma.export_to_mp3(audio, f"{temp_path}/{i}.mp3")
    
    # merge and save audio files now.
    concatenated_audio = ma.merge_audio(audio_files)
    ma.save(concatenated_audio, f"./audiobook_temps/{filename}.mp3")

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
    parser.add_argument("filename", type=str, help="The name of the file to process")

    args = parser.parse_args()

    with open(f"{args.filename}.txt", 'r') as file:
        text_content = file.read()

    # split the text into chunks of 500 characters or less (to lessen delay between input output. api limit is 5k characters)
    paragraphs = text_content.split("\n\n")
    chunks = []
    chunk = ""
    for paragraph in paragraphs:
        if len(chunk) + len(paragraph) > 500:
            chunks.append(chunk)
            chunk = ""
        if len(paragraph) > 1000:
            for sentence in paragraph.split('.'):
                if len(chunk) + len(sentence) > 500:
                    chunks.append(chunk)
                    chunk = ""
                chunk += sentence + "."
        else:
            chunk += paragraph + "\n\n"
    if chunk != "":
        chunks.append(chunk)

    # Start the producer thread
    producer_thread = threading.Thread(target=audio_producer, args=(chunks, args.filename,))
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