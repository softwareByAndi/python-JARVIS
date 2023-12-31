# TODO:
- [ ] refactor audio control functions into their own module.
- [ ] speech to text --> GPT --> custom logic --> GPT --> text to speech
- [ ] enable selection of other TTS APIs. 
  - perhaps Amazon Poly? it's 75x cheaper than eleven-labs, so good for testing.
  - playHT might be good too... 30% cheaper, and quality is okay.


# documentation: 

[elevenlabs-python github](https://github.com/elevenlabs/elevenlabs-python)
[openai documentation quickstart](https://platform.openai.com/docs/quickstart?context=python)


# dependencies
``` bash
pip install openai elevenlabs pydub python-dotenv pygame mutagen
```
``` bash 
sudo apt-get install ffmpeg mpv
```

# convert .txt to .mp3
``` bash
python tts.py infile.txt outfile_name # .mp3 will be appended automatically
```

<br>

# play audio

## play audio from terminal
``` bash
ffplay audio_file.mp3
```

## play audio using python pydub
``` python
from pydub import AudioSegment
from pydub.playback import play

# Load an audio file from your filesystem
sound = AudioSegment.from_mp3("path/to/your/file.mp3")

# Play the audio file
play(sound)
```

## generate audio from elevenlabs
``` python
from elevenlabs import generate, play, set_api_key
# api key is optional
set_api_key("api_key_here")

audio = generate(
  text="Hello! 你好! Hola! नमस्ते! Bonjour! こんにちは! مرحبا! 안녕하세요! Ciao! Cześć! Привіт! வணக்கம்!",
  voice="Bella",
  model="eleven_multilingual_v2"
)

play(audio)
```