import openai
import uuid
from datetime import datetime
from pathlib import Path
import os
from amdea import config
from amdea.brain.prompts import SYSTEM_PROMPT
from amdea.brain.schema import parse_and_validate
from amdea.security.keystore import get_api_key

async def get_task_plan(
    user_utterance: str,
    conversation_history: list[dict],
    detected_language: str = "en",
    active_browser_url: str | None = None,
    session_id: str = ""
) -> tuple[dict | None, str | None]:
    """
    Calls Groq (LPU) to generate a structured TaskPlan.
    """
    try:
        api_key = get_api_key("GROQ")
        client = openai.AsyncOpenAI(
            api_key=api_key, 
            base_url="https://api.groq.com/openai/v1",
            timeout=20.0
        )

        context_injection = (
            f"\n\nContext Information:\n"
            f"- detected_language={detected_language}\n"
            f"- active_browser_url={active_browser_url or 'none'}\n"
            f"- user_home={Path.home()}\n"
            f"- current_time={datetime.now().isoformat()}\n"
            f"- session_id={session_id}"
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + context_injection}
        ]
        
        # Add last N turns from history
        messages.extend(conversation_history[-config.MAX_CONVERSATION_TURNS:])
        
        # Add current user utterance
        messages.append({"role": "user", "content": user_utterance})

        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile", # Groq's fast & powerful model
            response_format={"type": "json_object"},
            messages=messages,
            temperature=0.1,
            max_tokens=2048
        )

        content = response.choices[0].message.content
        plan, error = parse_and_validate(content)
        if plan:
            # Always ensure a fresh, unique plan_id to avoid DB conflicts
            plan["plan_id"] = str(uuid.uuid4())
        return plan, error

    except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, Exception) as e:
        # Fallback to secondary Groq key if primary fails
        import logging
        logger = logging.getLogger("AMDEA")
        logger.warning(f"Primary Groq error: {str(e)}. Attempting fallback to secondary key...")
        
        try:
            # Try to get the secondary key from .env (the user added GROQ_API_KEY2)
            api_key2 = os.getenv("GROQ_API_KEY2")
            if not api_key2:
                raise ValueError("GROQ_API_KEY2 not found in .env")

            client2 = openai.AsyncOpenAI(
                api_key=api_key2, 
                base_url="https://api.groq.com/openai/v1",
                timeout=20.0
            )

            response = await client2.chat.completions.create(
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"},
                messages=messages,
                temperature=0.1,
                max_tokens=2048
            )

            content = response.choices[0].message.content
            plan, error = parse_and_validate(content)
            if plan:
                plan["plan_id"] = str(uuid.uuid4())
                logger.info("Successfully recovered using secondary Groq key.")
            return plan, error

        except Exception as fallback_err:
            logger.error(f"Fallback to secondary Groq key also failed: {str(fallback_err)}")
            return None, f"LLM error (Both Groq keys failed): {str(e)}"
