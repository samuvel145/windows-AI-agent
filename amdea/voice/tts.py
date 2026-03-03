import threading
import os
import asyncio
import numpy as np
import sounddevice as sd
from cartesia import AsyncCartesia
from amdea.security.keystore import get_api_key

# Default Cartesia Voice (Kiefer - American English)
DEFAULT_VOICE_ID = "228fca29-3a0a-435c-8728-5cb483251068"
MODEL_ID = "sonic-english"

class TTSPlayer:
    def __init__(self, voice_id: str = DEFAULT_VOICE_ID, model_id: str = MODEL_ID, sample_rate: int = 44100):
        self.voice_id = voice_id
        self.model_id = model_id
        self.sample_rate = sample_rate
        self._stop_event = threading.Event()
        self._is_playing = False
        self._client = None

    async def _get_client(self) -> AsyncCartesia:
        """Lazily initialize and reuse the AsyncCartesia client."""
        if not self._client:
            api_key = get_api_key("CARTESIA")
            self._client = AsyncCartesia(api_key=api_key)
        return self._client

    async def speak(self, text: str) -> None:
        """Streams text-to-speech from Cartesia to the speakers."""
        if not text:
            return

        try:
            client = await self._get_client()
            
            self._is_playing = True
            self._stop_event.clear()

            # Cartesia streaming output
            output_format = {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self.sample_rate,
            }

            # Use sounddevice stream for low-latency playback
            with sd.OutputStream(samplerate=self.sample_rate, channels=1, dtype='int16') as stream:
                gen = await client.tts.generate_sse(
                    model_id=self.model_id,
                    transcript=text,
                    voice={"id": self.voice_id}, 
                    output_format=output_format,
                )

                async for chunk in gen:
                    if self._stop_event.is_set():
                        break
                    
                    if hasattr(chunk, 'audio') and chunk.audio:
                        audio_data = np.frombuffer(chunk.audio, dtype=np.int16)
                        stream.write(audio_data)

        except Exception as e:
            from amdea.logging_config import get_logger
            get_logger("TTS").error(f"Cartesia TTS Error: {e}")
        finally:
            self._is_playing = False

    def interrupt(self) -> None:
        """Stops the current playback immediately."""
        self._stop_event.set()

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    async def speak_sync(self, text: str) -> None:
        """Convenience wrapper."""
        await self.speak(text)

    async def close(self):
        """Cleanly closes the Cartesia client."""
        if self._client:
            await self._client.close()
            self._client = None

async def speak_error(message: str) -> None:
    """Quickly announce an error."""
    player = TTSPlayer()
    try:
        await player.speak(message)
    finally:
        await player.close()
