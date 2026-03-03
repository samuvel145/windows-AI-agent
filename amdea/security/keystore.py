import keyring
import getpass
import argparse
import sys
import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

def store_api_key(service: str, key: str) -> None:
    """Saves API key to OS keychain."""
    keyring.set_password(f"AMDEA_{service}", "api_key", key)

def get_api_key(service: str) -> str:
    """Retrieves API key from environment variable or keychain (e.g., DEEPGRAM, GROQ, CARTESIA)."""
    # 1. Check environment variable (OPENAI_API_KEY)
    env_key = os.getenv(f"{service}_API_KEY")
    if env_key:
        return env_key
        
    # 2. Check keychain
    key = keyring.get_password(f"AMDEA_{service}", "api_key")
    if not key:
        raise EnvironmentError(f"AMDEA: {service} key not configured. Set {service}_API_KEY in .env or run setup.")
    return key

def delete_api_key(service: str) -> None:
    """Removes API key from keychain."""
    try:
        keyring.delete_password(f"AMDEA_{service}", "api_key")
    except keyring.errors.PasswordDeleteError:
        pass

def store_smtp_config(host: str, port: int, user: str, password: str, sender: str) -> None:
    """Stores all SMTP fields as separate keychain entries."""
    keyring.set_password("AMDEA_SMTP_host", "value", host)
    keyring.set_password("AMDEA_SMTP_port", "value", str(port))
    keyring.set_password("AMDEA_SMTP_user", "value", user)
    keyring.set_password("AMDEA_SMTP_password", "value", password)
    keyring.set_password("AMDEA_SMTP_sender", "value", sender)

def get_smtp_config() -> dict:
    """Returns SMTP config from environment or keychain."""
    config = {
        "host": os.getenv("SMTP_HOST") or keyring.get_password("AMDEA_SMTP_host", "value"),
        "port": os.getenv("SMTP_PORT") or keyring.get_password("AMDEA_SMTP_port", "value"),
        "user": os.getenv("SMTP_USER") or keyring.get_password("AMDEA_SMTP_user", "value"),
        "password": os.getenv("SMTP_PASSWORD") or keyring.get_password("AMDEA_SMTP_password", "value"),
        "sender": os.getenv("SMTP_SENDER") or keyring.get_password("AMDEA_SMTP_sender", "value")
    }
    if not all(v is not None for v in config.values()):
        raise EnvironmentError("AMDEA: SMTP configuration incomplete. Set SMTP_* variables in .env.")
    config["port"] = int(config["port"])
    return config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AMDEA Keystore Manager")
    args = parser.parse_args()
