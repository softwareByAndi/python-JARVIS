import sys
sys.path.append('../lib')
import merge_audio as ma
import eleven_labs_wrapper as el
import open_ai_wrapper as oa

prompt = oa.default_messages.get("recursion poem")
# prompt = oa.default_messages.get("cool historical fact")
text_response = oa.chat(prompt)

print(text_response)

# its probably fine to do this in a single call, 
# but I want some example code for concatenating audio files using AudioSegment
audio_files = [
  el.text_to_speech(paragraph) 
  for paragraph 
  in text_response.split("\n\n")
]

concatenated_audio = ma.merge_audio(audio_files)
ma.save(concatenated_audio)
ma.play(concatenated_audio)