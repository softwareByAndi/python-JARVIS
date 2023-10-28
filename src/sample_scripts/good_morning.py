import sys
sys.path.append('../../lib')
import eleven_labs_wrapper as el
import open_ai_wrapper as oa

good_morning_prompt = oa.default_messages.get("good morning")
text_response = oa.chat(good_morning_prompt)

audio = el.text_to_speech(text_response)
with open("good_morning.mp3", "wb") as f:
    f.write(audio)

el.play(audio)