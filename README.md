# AMDEA — Autonomous Multilingual Desktop Execution Agent

AMDEA is a powerful desktop execution agent that uses Voice Activity Detection (VAD), Speech-to-Text (STT), Large Language Models (LLM), and Desktop Automation to execute complex tasks from voice commands.

## Features
- **Voice First**: Hands-free interaction using VAD and high-quality STT/TTS.
- **Autonomous Planning**: Generates multi-step JSON plans using GPT-4o.
- **Safety First**: Multi-level risk classification and voice confirmation gates.
- **Rich Execution**: Controls applications, browsers, filesystem, email, and more.
- **Privacy Core**: OS-level keystore for API keys and encrypted/scrubbed logging.

## How it Works

AMDEA operates through a sophisticated 4-stage pipeline:

1.  **Voice Interaction Layer**: Uses `webrtcvad` for high-precision voice activity detection. Audio is processed using a custom zero-dependency header system and transcribed via **Deepgram Nova-2** for near-instant response.
2.  **LLM Brain**: The transcribed text is sent to **Groq** (with automatic failover to a secondary key). It generates a structured `TaskPlan` (JSON) using advanced semantic matching to map conversational intents to real system actions.
3.  **Safety Gate & Confirmation**: Every plan is validated by the Safety Controller. Actions are classified by risk level. High-risk actions trigger a voice-based confirmation gate.
4.  **Execution Engine**: Validated tasks are dispatched to specialized modules. Features include PowerShell-based app discovery, fuzzy file searching, and serialized event execution.

## API Key Setup

AMDEA requires API keys for its services. You can set them up using one of the following methods:

### Option 1: .env File (Recommended)
Create a `.env` file in the project root and add your keys:
```env
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
CARTESIA_API_KEY=your_cartesia_key
```

### Option 2: Setup Wizard
Run the interactive wizard to store keys securely in your system's keychain:
```bash
python -m amdea.main --setup
```

## Run Commands

The preferred way to run AMDEA is as a module from the project root:

| Command | Description |
|---------|-------------|
| `python -m amdea.main` | Starts the agent in standard mode. |
| `python -m amdea.main --setup` | Launches the interactive setup wizard for API keys. |
| `python -m amdea.main --safe-mode` | Forces the agent into a restricted demo mode. |
| `python -m amdea.main --version` | Displays the current version. |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AMDEA_SAFE_MODE` | `false` | When `true`, blocks critical actions and strictly limits file access. |
| `AMDEA_DEBUG` | `false` | Enables verbose debug logging to the terminal. |

## Supported Actions

AMDEA supports a wide range of autonomous actions:

| Action Category | Action Types |
|-----------------|--------------|
| **System** | `open_app`, `close_app`, `run_command` |
| **Browser** | `open_browser`, `navigate_url`, `browser_search`, `click_element` |
| **Filesystem** | `create_file`, `read_file`, `delete_file`, `list_folder` |
| **Communication** | `send_email`, `download_file` |
| **Interaction** | `type_text`, `key_press`, `wait`, `mouse_click` |

---
*AMDEA v0.1.0*
