import sys
sys.path.append('../../lib')
import open_ai_wrapper as oa

filepath = '../../assets/audio_files/concat_test.mp3'
audio_file = open(filepath, 'rb')
# transcript = oa.openai.Audio.transcribe(model="whisper-1", file=audio_file, response_format="json")
transcript = oa.openai.Audio.translate(model="whisper-1", file=audio_file, response_format="text")

print(transcript)
transcript_filename = filepath.split('/')[-1].replace('.mp3', '.txt')
with open(f"../../assets/transcripts/{transcript_filename}", 'w') as f:
    f.write(transcript["text"])