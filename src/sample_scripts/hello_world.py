import sys
sys.path.append('../../lib')
import eleven_labs_wrapper as el
import open_ai_wrapper as oa
import merge_audio as ma

voice_id_joe = "oGTpzH11KpZ0dMSJYpic"
voice_id_raj = "XP2Ab9U79SUgzE2L8PEK"

hello_world_prompt = oa.default_messages.get("hello world")
text_response = oa.chat(hello_world_prompt)

audio_result = el.text_to_speech(
    text_content=text_response,
    voice_id=voice_id_raj,
)

ma.export_to_mp3(audio_result)
el.play(audio_result)