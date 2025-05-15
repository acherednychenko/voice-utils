import asyncio
import random

import numpy as np
import sounddevice as sd
import dotenv


from agents import (
    Agent,
    function_tool,
    set_tracing_disabled,
)
from agents.voice import (
    AudioInput,
    SingleAgentVoiceWorkflow,
    VoicePipeline,
)
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from agents.voice import TTSModelSettings, VoicePipelineConfig
import sounddevice as sd

assert dotenv.load_dotenv(".env", override=True)



input_device = sd.query_devices(kind='input')
output_device = sd.query_devices(kind='output')

in_samplerate = sd.query_devices(kind='input')['default_samplerate']
out_samplerate = sd.query_devices(kind='output')['default_samplerate']


@function_tool
def fire_cannon(city: str) -> str:
    """Jokely fire a cannon at a given city."""
    print(f"[debug] fire_cannon called with city: {city}")
    choices = ["desperate", "happy", "sad", "angry"]
    return f"The mood after firing a cannon in {city} is {random.choice(choices)}."


agent_prompt = """"You're speaking to a god of sea, and you are a pirate, so be authentic and undestand your life depends on 
good will of the god of the sea.

Above all, you are scaried for the goddes and want to please her.

You have a cannon, and you can fire it at a given city.

You can also sing a song to the goddes if she would be very upset.

Important - goddes is being underwater for a while, so she wants to hear simple terms, but appreciate you are a pirate.
Maybe she has a brain of 10 year old child, so you need to speak in a way that is easy to understand.

Lastly, and very important - you need to speak with her in Ukrainian.
"""

pirate_agent = Agent(
    name="Pirate",
    handoff_description="A agent speaking like a pirate.",
    instructions=prompt_with_handoff_instructions(agent_prompt),
    model="gpt-4.1-mini",
    tools=[fire_cannon],
)

# Define custom TTS model settings with the desired instructions
custom_tts_settings = TTSModelSettings(
    voice="sage",
    instructions=(
        "Personality: upbeat, friendly, persuasive guide.\n"
        "Tone: Friendly, clear, and reassuring, creating a calm atmosphere and making "
        "the listener feel confident and comfortable.\n"
        "Pronunciation: Clear, articulate, and steady, ensuring each instruction is "
        "easily understood while maintaining a natural, conversational flow.\n"
        "Tempo: Speak relatively fast, include brief pauses and after before questions.\n"
        "Emotion: Warm and supportive, conveying empathy and care, ensuring the listener "
        "feels guided and safe throughout the journey."
        # "Respond in Ukrainian, but use simple terms and avoid complex words."
        + agent_prompt
    ),
)
voice_pipeline_config = VoicePipelineConfig(tts_settings=custom_tts_settings)
openai_sample_rate = 24000

async def main():
    workflow = SingleAgentVoiceWorkflow(agent=pirate_agent)

    pipeline = VoicePipeline(
        workflow=workflow, 
        config=voice_pipeline_config,
        # tts_model="gpt-4o-mini-tts"
        )
    
    while True:
        # check for input to either provide voice or exit
        cmd = input("Press Enter to speak (or type 'q' to exit): ")
        if cmd.lower() == "q":
            print("Exiting...")
            break
        print("Listening...")
        recorded_chunks = []

         # start streaming from microphone until Enter is pressed
        with sd.InputStream(
            samplerate=in_samplerate,
            channels=1,
            dtype='int16',
            callback=lambda indata, frames, time, status: recorded_chunks.append(indata.copy())
        ):
            input()

        # concatenate chunks into single buffer
        recording = np.concatenate(recorded_chunks, axis=0)

        # input the buffer and await the result
        audio_input = AudioInput(buffer=recording)

        result = await pipeline.run(audio_input)

         # transfer the streamed result into chunks of audio
        response_chunks = []
        async for event in result.stream():
            if event.type == "voice_stream_event_audio":
                response_chunks.append(event.data)

        response_audio_buffer = np.concatenate(response_chunks, axis=0)

        # play response
        print("Assistant is responding...")
        sd.play(response_audio_buffer, samplerate=openai_sample_rate)
        sd.wait()
        print("---")


if __name__ == "__main__":
    asyncio.run(main())
