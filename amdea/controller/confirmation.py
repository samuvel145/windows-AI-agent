import asyncio
from amdea import config
from amdea.voice.tts import TTSPlayer, speak_error
from amdea.voice.vad import VoiceActivityDetector
from amdea.voice.stt import transcribe

CONFIRMATION_PROMPTS = {
    "delete_file": "I'm about to permanently delete {path}. This cannot be undone. Say yes to confirm or cancel to stop.",
    "delete_file_glob": "This will delete all files matching the pattern. Are you sure? Say DELETE to confirm or cancel.",
    "send_email": "I'll send an email to {to} with subject {subject}. Say yes to confirm or cancel.",
    "download_file": "I'll download a file to {destination}. Say yes to proceed or cancel.",
    "run_command": "I'm about to run a system command. This can have significant effects. Say yes to confirm.",
    "move_file": "I'll move {source} to {destination}. Say yes to confirm or cancel.",
    "generic": "I'm about to perform a {action}. Say yes to confirm or cancel."
}

AFFIRMATIVE_WORDS = {"yes", "yeah", "confirm", "go ahead", "ok", "okay", "sure", "delete"}
NEGATIVE_WORDS = {"no", "cancel", "stop", "abort", "nope"}

async def request_confirmation(
    action_type: str,
    parameters: dict,
    tts_player: TTSPlayer,
    vad: VoiceActivityDetector,
    language: str = "en"
) -> bool:
    """Asks the user for voice confirmation before proceeding with a risky action."""
    
    # Select prompt
    if action_type == "delete_file" and ("glob" in parameters or "pattern" in parameters):
        prompt_tpl = CONFIRMATION_PROMPTS["delete_file_glob"]
    else:
        prompt_tpl = CONFIRMATION_PROMPTS.get(action_type, CONFIRMATION_PROMPTS["generic"])
    
    prompt = prompt_tpl.format(action=action_type, **parameters)
    
    print(f"CONFIRMATION REQUIRED: {prompt}")
    await tts_player.speak(prompt)
    
    # Wait for response via VAD
    response_audio = None
    response_received = asyncio.Event()

    def on_audio(audio):
        nonlocal response_audio
        response_audio = audio
        response_received.set()

    vad.start_listening(on_audio)
    
    try:
        # Wait for user to speak
        await asyncio.wait_for(response_received.wait(), timeout=config.CONFIRMATION_TIMEOUT_SECONDS)
        vad.stop_listening()
        
        # Transcribe
        result = await transcribe(response_audio)
        text = result["text"].lower().strip()
        print(f"User confirmation response: '{text}'")
        
        if any(word in text for word in AFFIRMATIVE_WORDS):
            return True
            
        if any(word in text for word in NEGATIVE_WORDS):
            await tts_player.speak("Action cancelled.")
            return False
            
        await tts_player.speak("I didn't catch that. Cancelling for safety.")
        return False

    except asyncio.TimeoutError:
        vad.stop_listening()
        await tts_player.speak("No response received. Action cancelled.")
        return False
    except Exception as e:
        vad.stop_listening()
        print(f"Confirmation Error: {e}")
        return False
