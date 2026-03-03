import collections
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import webrtcvad

class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 3, sample_rate: int = 16000,
                 frame_duration_ms: int = 30, silence_threshold_ms: int = 400):
        """
        Initializes the VAD.
        - aggressiveness: 0-3 (3 is most aggressive)
        - sample_rate: Must be 8000, 16000, 32000, or 48000 Hz.
        - frame_duration_ms: Must be 10, 20, or 30 ms.
        - silence_threshold_ms: Duration of silence to wait before ending speech.
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.silence_threshold_ms = silence_threshold_ms
        
        # Calculate frames per buffer
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.num_silence_frames = silence_threshold_ms // frame_duration_ms
        
        self.is_speaking = False
        self.on_speech_start: Optional[Callable] = None
        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()
        self._buffer = []
        self._listening_thread = None

    def _audio_callback(self, indata, frames, time, status):
        """Callback for sounddevice InputStream."""
        if status:
            from amdea.logging_config import get_logger
            get_logger("VAD").debug(f"VAD Audio Status: {status}")
        self._audio_queue.put(indata.copy())

    def start_listening(self, callback: Callable[[bytes], None]) -> None:
        """Starts the VAD loop in a daemon thread."""
        self._stop_event.clear()
        self._listening_thread = threading.Thread(target=self._run_vad_loop, args=(callback,), daemon=True)
        self._listening_thread.start()

    def _run_vad_loop(self, callback: Callable[[bytes], None]):
        """The core VAD processing loop with fixed-size chunking."""
        padding_duration_ms = 150
        num_padding_frames = padding_duration_ms // self.frame_duration_ms
        ring_buffer = collections.deque(maxlen=num_padding_frames)
        
        triggered = False
        speech_buffer = []
        silence_counter = 0

        # Internal buffer to handle arbitrary block sizes from soundcard
        raw_audio_buffer = bytearray()
        bytes_per_frame = self.frame_size * 2 # 16-bit mono

        # blocksize=0 allows sounddevice to pick the most efficient size
        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16',
                            callback=self._audio_callback):
            # Warm up the mic buffer by draining first 0.5 seconds silently
            import time as _time
            _warmup_end = _time.time() + 0.5
            while _time.time() < _warmup_end and not self._stop_event.is_set():
                try:
                    self._audio_queue.get(timeout=0.1)
                except queue.Empty:
                    pass

            while not self._stop_event.is_set():
                try:
                    data = self._audio_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                raw_audio_buffer.extend(data.tobytes())

                # Process all complete frames in the buffer
                while len(raw_audio_buffer) >= bytes_per_frame:
                    frame_bytes = bytes(raw_audio_buffer[:bytes_per_frame])
                    del raw_audio_buffer[:bytes_per_frame]
                    
                    frame = np.frombuffer(frame_bytes, dtype=np.int16)
                    is_speech = self.vad.is_speech(frame_bytes, self.sample_rate)

                    if not triggered:
                        ring_buffer.append((frame, is_speech))
                        num_voiced = len([f for f, speech in ring_buffer if speech])
                        if num_voiced > 0.5 * ring_buffer.maxlen:
                            triggered = True
                            self.is_speaking = True
                            if self.on_speech_start:
                                self.on_speech_start()
                                
                            # Flush ring buffer into speech buffer
                            for f, s in ring_buffer:
                                speech_buffer.append(f)
                            ring_buffer.clear()
                    else:
                        speech_buffer.append(frame)
                        if not is_speech:
                            silence_counter += 1
                        else:
                            silence_counter = 0

                        if silence_counter >= self.num_silence_frames:
                            # Speech ended
                            full_audio = np.concatenate(speech_buffer).tobytes()
                            callback(full_audio)
                            
                            # Reset for next utterance
                            triggered = False
                            self.is_speaking = False
                            speech_buffer = []
                            silence_counter = 0

    def stop_listening(self) -> None:
        """Stops the listening loop."""
        self._stop_event.set()
        if self._listening_thread:
            self._listening_thread.join(timeout=2.0)
