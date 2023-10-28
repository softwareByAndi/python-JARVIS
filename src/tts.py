import sys
sys.path.append('../lib')
import argparse
import eleven_labs_wrapper as el
import merge_audio as ma

if (__name__ == "__main__"):
    parser = argparse.ArgumentParser(description="process a filename.")
    parser.add_argument("infile", type=str, help="the name of the file to process")
    parser.add_argument("outfile", type=str, help="the name of the file to process")

    args = parser.parse_args()
    print(args.infile)
    print(args.outfile)

    with open(args.infile, 'r') as file:
        text_content = file.read()
        
    audio = el.text_to_speech(text_content)
    ma.export_to_mp3(audio, f"{args.outfile}.mp3")
    el.play(audio)
        
    
    
else:
    print("This file is intended to be run as a script, not imported as a module.")
    exit(1)