from elevenlabs import generate, stream, set_api_key
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Retrieve API Key
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')

# Check if the API key exists
if ELEVENLABS_API_KEY is None:
    print("ELEVENLABS_API_KEY environment variable is not set.")
    exit(1)

# Set API Key
set_api_key(ELEVENLABS_API_KEY)

def text_stream(paragraphs):
    for paragraph in paragraphs:
        yield paragraph

# Your array of paragraphs
paragraphs = """In the realm of code where wonders arise,
Lies a concept mysterious, where logic defies.
Recursion, they call it, a programming spell,
Unraveling the beauty in a loop as well.

Imagine a puzzle, piece by piece,
Recursive wonders, never to cease.
With elegance divine, it begins its dance,
A self-referential, mesmerizing trance.

A function profound, it calls upon,
Itself, my dear, a loop never done.
Like a mirror reflecting its own reflection,
Recursion echoes, in infinite reflection.

Through layers of calls, it travels deep,
A path unfolding, secrets to keep.
As each cycle ends, a story unfurls,
Expanding the world, breaking old rules.

Like nesting dolls, it peels away,
Solving problems large, finding the way.
From the grandest task to the simplest chore,
Recursion's embrace opens countless doors."""

audio_stream = generate(
    # text=text_stream(paragraphs.split("\n\n")),
    text=paragraphs,
    voice="Valentino",
    model="eleven_multilingual_v2",
    stream=True
)

stream(audio_stream)
