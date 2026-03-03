import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from amdea.main import AgentCore

@pytest.mark.asyncio
async def test_safety_gate_denial():
    """
    E2E scenario: 
    1. User says "delete my downloads"
    2. LLM plans a 'delete_file' with glob.
    3. Controller sees high risk, asks for confirmation.
    4. User says "no" or "cancel".
    5. Action is blocked, task fails/cancels gracefully.
    """
    agent = AgentCore()
    agent.tts.speak = AsyncMock()
    
    plan = {
        "plan_id": "e2e-delete",
        "detected_language": "en",
        "intent_summary": "Delete downloads",
        "steps": [{
            "step_id": 1,
            "action_type": "delete_file",
            "parameters": {"path": "~/Downloads", "glob": "*"},
            "requires_confirmation": True
        }],
        "tts_response": "Deleting your downloads."
    }

    # Mock STT for confirmation: User says "No don't do that"
    with patch("amdea.main.transcribe", AsyncMock(return_value={"text": "delete my downloads", "language": "en"})), \
         patch("amdea.main.get_task_plan", AsyncMock(return_value=(plan, None))), \
         patch("amdea.controller.confirmation.VoiceActivityDetector", MagicMock()), \
         patch("amdea.controller.confirmation.transcribe", AsyncMock(return_value={"text": "no stop", "language": "en"})), \
         patch("amdea.execution.filesystem.delete_files_glob", MagicMock()) as mock_delete:
        
        # Start handling the initial command
        await agent._handle_audio(b"delete_cmd")
        
        # Verify filesystem was NOT touched
        mock_delete.assert_not_called()
        # Verify it spoke some form of cancellation
        # The confirmation logic in confirmation.py returns False, then task_controller calls cancel_task
        # We check the TTS calls
        calls = [c.args[0].lower() for c in agent.tts.speak.call_args_list]
        # One call for the confirmation prompt, one for the cancellation acknowledgement (optional in implementation)
        assert any("are you sure" in c or "confirm" in c for c in calls)

@pytest.mark.asyncio
async def test_safety_gate_approval():
    """
    E2E scenario: User says "yes" to confirmation and action proceeds.
    """
    agent = AgentCore()
    agent.tts.speak = AsyncMock()
    
    plan = {
        "plan_id": "e2e-delete-ok",
        "detected_language": "en",
        "steps": [{
            "step_id": 1,
            "action_type": "delete_file",
            "parameters": {"path": "~/Downloads", "glob": "temp_*"},
            "requires_confirmation": True
        }],
        "tts_response": "Done."
    }

    with patch("amdea.main.transcribe", AsyncMock(return_value={"text": "clean temp", "language": "en"})), \
         patch("amdea.main.get_task_plan", AsyncMock(return_value=(plan, None))), \
         patch("amdea.controller.confirmation.transcribe", AsyncMock(return_value={"text": "yes please", "language": "en"})), \
         patch("amdea.execution.filesystem.delete_files_glob", MagicMock()) as mock_delete:
        
        await agent._handle_audio(b"audio")
        
        # Verify filesystem WAS touched
        mock_delete.assert_called_once()
