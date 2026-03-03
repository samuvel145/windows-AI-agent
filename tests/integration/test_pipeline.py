import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from amdea.main import AgentCore

@pytest.mark.asyncio
async def test_full_pipeline_success():
    """
    Tests the flow: transcript -> LLM Plan -> Safety Check -> Execution.
    Mocks the voice input and LLM response.
    """
    agent = AgentCore()
    
    # Mock transcript and plan
    transcript = "open notepad"
    plan = {
        "plan_id": "test-p-1",
        "detected_language": "en",
        "intent_summary": "Opening notepad",
        "steps": [{
            "step_id": 1,
            "action_type": "open_app",
            "parameters": {"app_name": "notepad"},
            "requires_confirmation": False
        }],
        "tts_response": "I'm opening Notepad for you."
    }

    # Mock dependencies
    with patch("amdea.main.transcribe", AsyncMock(return_value={"text": transcript, "language": "en"})), \
         patch("amdea.main.get_task_plan", AsyncMock(return_value=(plan, None))), \
         patch("amdea.controller.task_controller.app_control.open_app", MagicMock()) as mock_open:
        
        # We need to mock the TTS speak to avoid actual audio output in tests
        agent.tts.speak = AsyncMock()
        
        # Simulate audio arrival
        await agent._handle_audio(b"fake_audio_bytes")
        
        # Verify
        mock_open.assert_called_once_with("notepad", [])
        agent.tts.speak.assert_called_with("I'm opening Notepad for you.")

@pytest.mark.asyncio
async def test_pipeline_safety_block():
    """Tests that an unsafe plan is blocked before execution."""
    agent = AgentCore()
    
    plan = {
        "plan_id": "unsafe-1",
        "detected_language": "en",
        "steps": [{
            "step_id": 1,
            "action_type": "run_command", # Critical risk
            "parameters": {"command": "rm -rf /"},
            "requires_confirmation": False
        }],
        "tts_response": "Deleting everything."
    }

    with patch("amdea.main.transcribe", AsyncMock(return_value={"text": "delete all", "language": "en"})), \
         patch("amdea.main.get_task_plan", AsyncMock(return_value=(plan, None))):
        
        agent.tts.speak = AsyncMock()
        
        await agent._handle_audio(b"audio")
        
        # Controller's execute_plan should have spoken a safety warning instead of deleting
        # In current main._handle_audio, it calls controller.execute_plan which does safety check
        args, _ = agent.tts.speak.call_args
        assert "safely" in args[0] or "safety reasons" in args[0]
