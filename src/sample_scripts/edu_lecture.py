import sys
sys.path.append('../../lib')
from datetime import datetime
import eleven_labs_wrapper as el
import open_ai_wrapper as oa
import merge_audio as ma


timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"Custom formatted timestamp: {timestamp_str}")

transcript_prompt = [
    { "role": "system", "content": "you are a masterful professor of nano electronics and cpu architecture, and you're about to give you're favorite lecture. You're in the middle of your lecture, and you're about to explain the basics of nano electronics and cpu architecture. you say, "},
    { "role": "user", "content": "give a lecture on the basics of nano electronics and cpu architecture."}
]
transcript = oa.chat(transcript_prompt)


with open(f"../../assets/transcripts/edu_lecture {timestamp_str} (raw).txt", 'w') as f:
    f.write(transcript)
print(transcript)


print('\n\n\n--------------------------------------------------------------------------------------\n\n\n')


# editor_prompt = [
#     { "role": "system", "content": "you are a masterful writer and you've been hired on to edit the transcript of a lecture on the basics of nano electronics and cpu architecture. the transcript is a bit dry, and you've been asked to spice it up a bit."},
#     { "role": "user", "content": transcript}
# ]
# editorial = oa.chat(editor_prompt)
# with open(f"../../assets/transcripts/edu_lecture {timestamp_str} (editorial).txt", 'w') as f:
#     f.write(editorial)
# print(editorial)


# print('\n\n\n--------------------------------------------------------------------------------------\n\n\n')


peer_review_prompt = [
    { "role": "system", "content": "you are a masterful professor of nano electronics and cpu architecture. You've been tasked with peer reviewing the transcript of a fellow professor. Although your job is to make sure the transcript is accurate and that the edits are appropriate, you decide add a witty and satirical twist to the transcript emphasizing your well practiced dry humor. Please fix any errors and make any changes you see fit."},
    { "role": "user", "content": transcript}
]
peer_review = oa.chat(peer_review_prompt)
with open(f"../../assets/transcripts/edu_lecture {timestamp_str} (peer reviewed).txt", 'w') as f:
    f.write(peer_review)
print(peer_review)


# translating this to speech is a good way to use up all of my tokens... review and edit the transcript first, then use tts.py to generate the audio