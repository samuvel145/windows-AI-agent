import sys
import os

# Add parent directory to sys.path to allow running as a script from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import argparse
import uuid
import time
import getpass
import httpx
from amdea import config
from amdea.memory.database import init_db
from amdea.voice.vad import VoiceActivityDetector
from amdea.voice.stt import transcribe, STTTimeoutError
from amdea.voice.tts import TTSPlayer, speak_error
from amdea.controller.task_controller import TaskController
from amdea.brain.llm import get_task_plan
from amdea.memory import conversation, custom_commands
from amdea.security import keystore
from amdea.logging_config import setup_logging, get_logger, scrub_secrets
from amdea.gui.tray import SystemTray

logger = get_logger("AMDEA")

class AgentCore:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.loop = asyncio.get_running_loop()
        self.tts = TTSPlayer()
        self.vad = VoiceActivityDetector(silence_threshold_ms=config.SILENCE_TIMEOUT_MS)
        self.controller = TaskController(self.tts, self.vad)
        self.controller.session_id = self.session_id
        self.is_running = False
        self._pending_audio = asyncio.Queue()
        self._execution_lock = asyncio.Lock()
        self.tray = None

    async def start(self) -> None:
        init_db()
        logger.info(f"AMDEA starting session {self.session_id}")
        
        # Wire VAD FIRST — so we're listening from the moment the app starts
        def on_speech(audio):
            self.loop.call_soon_threadsafe(self._pending_audio.put_nowait, audio)

        def on_speech_start():
            if self.tts.is_playing:
                self.tts.interrupt()
            if self.tray:
                self.tray.set_state("LISTENING")

        self.vad.on_speech_start = on_speech_start
        self.vad.start_listening(callback=on_speech)
        self.is_running = True
        
        # Run health check in the background — don't block startup
        asyncio.create_task(self._run_health_check())
        
        # Greeting plays in background while mic is already active
        asyncio.create_task(self.tts.speak("Hello! I am AMDEA, your desktop assistant. Listening now."))

        while self.is_running:
            audio = await self._pending_audio.get()
            # Process each utterance in a background task so STT/LLM can happen concurrently
            asyncio.create_task(self._handle_audio(audio))

    async def _run_health_check(self):
        """Runs health check in background and logs issues silently."""
        try:
            health = await health_check()
            if health["status"] == "error":
                logger.warning(f"Health check issues: {health['issues']}")
        except Exception as e:
            logger.error(f"Health check failed: {e}")

    async def _handle_audio(self, audio: bytes) -> None:
        if self.tray: self.tray.set_state("PROCESSING")
        try:
            # 1. STT
            stt_result = await transcribe(audio)
            transcript = stt_result["text"]
            language = stt_result["language"]
            if not transcript.strip():
                return
            
            logger.info(f"User: {transcript} [{language}]")
            
            # 2. Custom Command
            custom = custom_commands.get_command(transcript)
            if custom:
                import json
                plan = json.loads(custom["plan_json"])
                plan["detected_language"] = language
                if self.tray: self.tray.set_state("PROCESSING")
                await self.controller.execute_plan(plan, language)
                return

            # 3. Save Memory
            conversation.add_turn(self.session_id, "user", transcript, language)

            # 4. Generate & Execute Plan
            plan, error = await get_task_plan(
                transcript, 
                conversation.get_recent_turns(self.session_id),
                language,
                self.controller.active_browser_url,
                self.session_id
            )

            if error:
                friendly_error = f"Sorry, I couldn't process that. {error}"
                await self.tts.speak(friendly_error)
                return

            if plan:
                logger.info(f"Generated Plan: {plan.get('intent_summary', 'No summary')}")
                logger.debug(f"Plan steps: {plan.get('steps')}")

            # 5. Handle Clarification
            if plan.get("clarification_needed"):
                q = plan["clarification_question"]
                logger.info(f"Assistant (Clarify): {q}")
                conversation.add_turn(self.session_id, "assistant", q, language)
                if self.tray: self.tray.set_state("SPEAKING")
                await self.tts.speak(q)
                return

            # 6. Execute (Serialized via Lock to prevent overlapping actions)
            async with self._execution_lock:
                if self.tray: self.tray.set_state("PROCESSING")
                await self.controller.execute_plan(plan, language)
                if self.tray: self.tray.set_state("IDLE")

            # 7. Final Response is spoken by controller.execute_plan

        except STTTimeoutError:
            logger.warning("STT timed out")
            try:
                await self.tts.speak("Sorry, I couldn't hear you clearly.")
            except Exception:
                pass
        except asyncio.CancelledError:
            # Task cancelled during execution (e.g., shutdown)
            raise
        except Exception as e:
            # If it's a known 'empty' or 'silent' error, ignore it
            if "empty" in str(e).lower() or "silence" in str(e).lower():
                return
                
            logger.error(f"Handle Audio Error: {e}")
            try:
                # Only speak serious errors that the user needs to hear
                if not any(token in str(e).lower() for token in ["cancelled", "interrupted"]):
                    await self.tts.speak("Something went wrong with the voice request. Please try again.")
            except Exception:
                logger.debug("TTS failed during error feedback — likely no internet.")

    def stop(self) -> None:
        self.vad.stop_listening()
        self.is_running = False
        from amdea.execution.browser import close_browser
        asyncio.create_task(close_browser())
        logger.info("AMDEA stopping")

def setup_wizard():
    print("\n" + "="*40)
    print("      AMDEA SETUP WIZARD")
    print("="*40)
    print("Note: Characters will be HIDDEN for security when typing API keys.")
    print("Just paste/type and press Enter.\n")
    
    try:
        dg_key = getpass.getpass("Enter your Deepgram API key (STT): ").strip()
        if dg_key:
            keystore.store_api_key("DEEPGRAM", dg_key)
            print("✓ Deepgram API Key stored.")

        groq_key = getpass.getpass("Enter your Groq API key (LLM): ").strip()
        if groq_key:
            keystore.store_api_key("GROQ", groq_key)
            print("✓ Groq API Key stored.")

        cart_key = getpass.getpass("Enter your Cartesia API key (TTS): ").strip()
        if cart_key:
            keystore.store_api_key("CARTESIA", cart_key)
            print("✓ Cartesia API Key stored.")
        
        print("\n--- Optional: Email Configuration ---")
        # ... rest remains similar but keeping it for context
        do_smtp = input("Do you want to configure email (SMTP) for sending? [y/N]: ").lower() == 'y'
        if do_smtp:
            host = input("SMTP Host (e.g. smtp.gmail.com): ")
            port = input("SMTP Port (e.g. 465): ")
            user = input("SMTP User: ")
            pw = getpass.getpass("SMTP Password (hidden): ")
            sender = input("Sender Email Address: ")
            keystore.store_smtp_config(host, port, user, pw, sender)
            print("✓ SMTP configuration stored.")

        print("\n" + "="*40)
        print("Setup complete! You can now start AMDEA.")
        print("Run: python -m amdea.main")
        print("="*40)
        
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during setup: {e}")
        sys.exit(1)

async def health_check() -> dict:
    issues = []
    # 1. Key check
    providers = ["DEEPGRAM", "GROQ", "CARTESIA"]
    for p in providers:
        try: keystore.get_api_key(p)
        except EnvironmentError as e: issues.append(str(e))

    # 2. Connectivity & API Check
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Groq check
        try:
            g_key = keystore.get_api_key("GROQ")
            if g_key and "your_" not in g_key:
                r = await client.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {g_key}"})
                # 400/401/403 means the server is there, but our key/request is bad.
                # Only serious connect errors or 5xx are "unreachable"
                if r.status_code >= 500:
                    issues.append(f"Groq server issue (HTTP {r.status_code}).")
            else:
                issues.append("GROQ_API_KEY is not set or using dummy value in .env")
        except Exception as e: 
            issues.append(f"Could not reach Groq API: {type(e).__name__} {str(e)}")
        
        # Deepgram check
        try:
            dg_key = keystore.get_api_key("DEEPGRAM")
            if dg_key and "your_" not in dg_key:
                r = await client.get("https://api.deepgram.com/v1/projects", headers={"Authorization": f"Token {dg_key}"})
                if r.status_code >= 500:
                    issues.append(f"Deepgram server issue (HTTP {r.status_code}).")
            else:
                issues.append("DEEPGRAM_API_KEY is not set or using dummy value in .env")
        except Exception as e:
            issues.append(f"Could not reach Deepgram API: {type(e).__name__} {str(e)}")

    # 3. Sound check
    try:
        import sounddevice as sd
        sd.query_devices(kind="input")
    except Exception: issues.append("No active microphone detected.")
    
    # 4. Playwright check
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            if not os.path.exists(p.chromium.executable_path):
                issues.append("Playwright Chromium executable not found.")
    except Exception as e:
        issues.append(f"Playwright check failed: {str(e)}. Run: python -m playwright install chromium")
    
    # FFmpeg check (Optional now)
    # import shutil
    # if not shutil.which("ffmpeg"):
    #     issues.append("FFmpeg not found.")
    
    return {"status": "error" if issues else "ok", "issues": issues}

def parse_args():
    parser = argparse.ArgumentParser(description=f"AMDEA v{config.VERSION}")
    parser.add_argument("--setup", action="store_true", help="Run initial setup wizard")
    parser.add_argument("--safe-mode", action="store_true", help="Enable safe demo mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version=f"AMDEA v{config.VERSION}")
    return parser.parse_args()

async def async_main():
    args = parse_args()
    if args.setup:
        setup_wizard()
        return

    if args.safe_mode:
        os.environ["AMDEA_SAFE_MODE"] = "true"
    if args.debug:
        os.environ["AMDEA_DEBUG"] = "true"

    setup_logging()
    
    agent = AgentCore()
    tray = SystemTray(agent)
    agent.tray = tray
    tray.run()
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        agent.stop()
        tray.stop()

if __name__ == "__main__":
    asyncio.run(async_main())
