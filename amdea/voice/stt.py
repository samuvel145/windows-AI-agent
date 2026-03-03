import io
import asyncio
import struct
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)
from amdea.security.keystore import get_api_key

class STTError(Exception): pass
class STTTimeoutError(STTError): pass
class STTAuthError(STTError): pass

# Cache the client to avoid re-instantiation overhead
_dg_client = None

def _create_wav_header(sample_rate: int, num_channels: int, sample_width: int, data_size: int) -> bytes:
    """Creates a minimal WAV header for RAW PCM data."""
    header = bytearray(b'RIFF')
    header.extend(struct.pack('<I', 36 + data_size))
    header.extend(b'WAVEfmt ')
    header.extend(struct.pack('<I', 16)) # Subchunk1Size
    header.extend(struct.pack('<H', 1))  # AudioFormat (PCM)
    header.extend(struct.pack('<H', num_channels))
    header.extend(struct.pack('<I', sample_rate))
    header.extend(struct.pack('<I', sample_rate * num_channels * sample_width))
    header.extend(struct.pack('<H', num_channels * sample_width))
    header.extend(struct.pack('<H', sample_width * 8))
    header.extend(b'data')
    header.extend(struct.pack('<I', data_size))
    return bytes(header)

async def transcribe(audio_pcm: bytes, sample_rate: int = 16000) -> dict:
    """
    Sends raw PCM audio to Deepgram for transcription.
    Returns {"text": str, "language": str}.
    """
    global _dg_client
    try:
        if not _dg_client:
            api_key = get_api_key("DEEPGRAM")
            _dg_client = DeepgramClient(api_key)

        # Faster conversion: Manual WAV header instead of pydub/ffmpeg
        header = _create_wav_header(sample_rate, 1, 2, len(audio_pcm))
        wav_data = header + audio_pcm
        
        source = {'buffer': wav_data, 'mimetype': 'audio/wav'}
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            detect_language=True,
            punctuate=True,
        )

        response = await asyncio.wait_for(
            _dg_client.listen.asyncprerecorded.v("1").transcribe_file(source, options),
            timeout=15.0
        )
        
        transcript = response.results.channels[0].alternatives[0].transcript
        detected_lang = response.results.channels[0].detected_language or "en"
        
        return {
            "text": transcript.strip(),
            "language": detected_lang
        }

    except asyncio.TimeoutError:
        raise STTTimeoutError("Deepgram transcription timed out. Check your internet connection.")
    except Exception as e:
        err_str = f"{type(e).__name__}: {str(e)}"
        if "401" in err_str or "Unauthorized" in err_str:
            raise STTAuthError("Invalid Deepgram API key. Check your .env file.")
        raise STTError(f"Deepgram Error: {err_str}")
