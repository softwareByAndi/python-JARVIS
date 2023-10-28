import os
import sys
sys.path.append('../lib')
from datetime import datetime
from time import sleep
import threading
import queue
import argparse
import eleven_labs_wrapper as el
import merge_audio as ma

# Initialize a thread-safe queue
audio_queue = queue.Queue()
MAX_QUEUE_SIZE = 4
HARD_CHARACTER_LIMIT = 5000
PRICE_PER_1K_CHARACTERS = 0.3
PRICE_PER_CHARACTER = PRICE_PER_1K_CHARACTERS / 1000

DEFAULT_COST_LIMIT = 3.00 # $3.00
cost_limit = DEFAULT_COST_LIMIT

timestamp_str = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
print(f"Custom formatted timestamp: {timestamp_str}")

def audio_producer(text_chunks, filepath, filename):
    audio_files = []
    temp_path = f"{filepath}{filename}/temp/{timestamp_str}"
    os.makedirs(temp_path, exist_ok=True)
    
    for i, paragraph in enumerate(text_chunks):
        # Check if queue has reached size limit
        while audio_queue.qsize() >= MAX_QUEUE_SIZE:
            sleep(1)  # Wait for 1000 milliseconds before checking again
          
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
    
    # GET CMD LINE ARGUMENTS
    parser = argparse.ArgumentParser(description="Process a filename.")
    parser.add_argument("file", type=str, help="The name of the file to process")
    parser.add_argument("--cost_limit", type=float, default=DEFAULT_COST_LIMIT, help="Maximum amount to spend. don't translate any more if the cost of the conversion will exceed this amount.")
    parser.add_argument("--convert_until_limit", action="store_true", help="If true, the script will convert as much as possible up until the cost limit. If false, the script will not execute if the total conversion will exceed the cost limit.")

    args = parser.parse_args()
    cost_limit = args.cost_limit
    if (args.file == None):
        print("No filename provided.")
        exit(1)
    if (args.file.split('.')[-1] != 'txt'):
        print("File must be a .txt file.")
        exit(1)
        
    _filepath_parts = args.file.split('/')[:-1]
    _filepath_string = '/'.join(_filepath_parts)
    filepath = f"./{_filepath_string}/" # note the postfixed /
    filename = args.file.split('/')[-1].replace('.txt', '')
    
    print(f"filepath: {filepath}")
    print(f"filename: {filename}")

    # READ FILE CONTENTS
    with open(f"{filepath}{filename}.txt", 'r') as file:
        text_content = file.read()
    

    # PRINT FILE DETAILS AND ESTIMATED COST
    print('')
    print(f"Number of characters: {len(text_content)}")
    print(f"Estimated cost: ${round(len(text_content) * PRICE_PER_CHARACTER, 2)}")
    print('')
    print(f"Cost limit: ${round(cost_limit, 2)}")
    print(f"Convert until limit: {args.convert_until_limit}")
    
    if (not args.convert_until_limit and len(text_content) * PRICE_PER_CHARACTER > cost_limit):
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
        { "index": 16, "chunk_size": HARD_CHARACTER_LIMIT }
    ]
    char_limit_stage_index = 0
    
    paragraphs = [paragraph for paragraph in text_content.split("\n\n") if paragraph.strip() != ""]
    chunks = []
    chunk = ""
    for paragraph in paragraphs:
        try:
            # check if we've reached the next stage
            next_chunk_index = character_limit_stages[char_limit_stage_index + 1]["index"]
            if len(chunks) >= next_chunk_index:
                char_limit_stage_index += 1
        except:
            pass
        
        # adjust the character limit based on the current stage
        character_limit = character_limit_stages[char_limit_stage_index]["chunk_size"]
        
        if len(chunk) + len(paragraph) > character_limit:
            chunks.append(chunk)
            chunk = ""
        if len(paragraph) > character_limit:
            for sentence in paragraph.split('.'):
                if len(chunk) + len(sentence) > character_limit:
                    chunks.append(chunk)
                    chunk = ""
                if len(sentence) > HARD_CHARACTER_LIMIT:
                    raise Exception(f"Sentence is too long to be processed by the API. current limit is {HARD_CHARACTER_LIMIT} characters.")
                chunk += sentence + "."
        else:
            chunk += paragraph + "\n\n"
    if chunk != "":
        chunks.append(chunk)
        
    
    
    
    # GET LIST CHUNKS WITHIN COST LIMIT
    chunks_to_convert = []
    sum_price = 0
    for chunk in chunks:
        chunk_price = len(chunk) * PRICE_PER_CHARACTER
        if sum_price + chunk_price > cost_limit:
            break
        chunks_to_convert.append(chunk)
        sum_price += chunk_price
        
    
    
    # USER CONFIRMATION
    num_chunks = len(chunks_to_convert)
    print('')
    print(f"number of chunks to convert:  {num_chunks} / {len(chunks)}")
    print(f"length of first {num_chunks} chunks:    {sum([len(chunk) for chunk in chunks_to_convert])} / {len(text_content)} characters")
    print(f"price of first {num_chunks} chunks:     ${sum_price}")
    
    print('')
    print(f"\na buffer of only {MAX_QUEUE_SIZE} audio chunks will be converted at any given time.")
    print(f"\nas audio plays, and chunks are removed from the queue, new chunks will be added to the queue until all chunks have been converted.")
    print(f"\neach audio chunk is saved in the temps folder upon conversion. if the program quits early, the individual mp3 files can still be found in the temps folder.")
    print(f"\nif the program finishes successfully, all chunks will be merged, and the final audio file will be saved next to the origin text file.")
    
    print('')
    confirmation = input("Do you want to continue? (y/n): ")
    if confirmation.lower() != 'y':
        print("Exiting program.")
        exit()
    
    # PERMISSION GRANTED
    # START THREADS

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