import asyncio
import time
import uuid
import traceback
import collections
import pathlib
from amdea import config
from amdea.brain import llm
from amdea.controller import safety, confirmation
from amdea.memory import conversation, task_history, custom_commands
from amdea.execution import app_control, browser, filesystem, keyboard_mouse, email_sender, downloader
from amdea.voice.tts import TTSPlayer, speak_error
from amdea.voice.vad import VoiceActivityDetector
from amdea.logging_config import get_logger

logger = get_logger("Controller")

class TaskController:
    def __init__(self, tts_player: TTSPlayer, vad: VoiceActivityDetector):
        self.tts = tts_player
        self.vad = vad
        self.active_plan = None
        self.session_id = str(uuid.uuid4())
        self.last_read_result = None
        self._cancelled = False
        self.active_browser_url = None

    async def execute_plan(self, plan: dict, language: str = "en"):
        try:
            plan_id = plan["plan_id"]
            intent = plan.get("intent_summary", "Task execution")
            steps = plan.get("steps", [])
            
            logger.info(f"Registering task {plan_id} in database...")
            task_history.create_task(plan_id, self.session_id, intent, len(steps))
        except KeyError as e:
            logger.error(f"Plan missing required key: {e}")
            await self.tts.speak("I received an invalid plan and cannot proceed.")
            return
        except Exception as e:
            logger.error(f"Error during initial task setup: {e}", exc_info=True)
            await self.tts.speak("An unexpected error occurred during task setup.")
            return

        start_time = time.time()
        steps_done = 0
        
        # Safety Check
        is_safe, safety_errors = safety.validate_plan_safety(plan)
        if not is_safe:
            msg = "I can't do that safely: " + "; ".join(safety_errors)
            await self.tts.speak(msg)
            task_history.fail_task(plan_id, 0, str(safety_errors), 0)
            return

        # Topological Sort
        try:
            ordered_steps = self._topological_sort(steps)
        except Exception as e:
            await self.tts.speak("I couldn't figure out the step order.")
            task_history.fail_task(plan_id, 0, f"Sort error: {e}", 0)
            return

        completed_step_ids = set()
        try:
            for step in ordered_steps:
                if self._cancelled:
                    break

                step_id = step["step_id"]
                action = step["action_type"]
                params = step["parameters"]
                
                # Check dependencies
                if not all(dep in completed_step_ids for dep in step.get("depends_on", [])):
                    logger.warning(f"Skipping Step {step_id}: Dependencies {step.get('depends_on')} not met. Completed: {completed_step_ids}")
                    continue

                logger.info(f"Executing Step {step_id}: {action} {params}")

                # Confirmation gate
                if step.get("requires_confirmation") and not step.get("confirmed"):
                    confirmed = await confirmation.request_confirmation(
                        action, params, self.tts, self.vad, language
                    )
                    if not confirmed:
                        task_history.cancel_task(plan_id, steps_done)
                        return
                    step["confirmed"] = True
                
                # Execute with retry
                outcome, error = await self._execute_step_with_retry(step, plan_id)
                if outcome == "success":
                    steps_done += 1
                    completed_step_ids.add(step_id)
                else:
                    if step.get("on_failure", "abort") == "abort":
                        raise Exception(error)
            
            # Final success
            duration = int((time.time() - start_time) * 1000)
            task_history.complete_task(plan_id, steps_done, duration)
            
            resp = plan.get("tts_response", "Done.")
            conversation.add_turn(self.session_id, "assistant", resp, language)
            await self.tts.speak(resp)

        except Exception as e:
            logger.error(f"Task Failed: {e}", exc_info=True)
            duration = int((time.time() - start_time) * 1000)
            task_history.fail_task(plan_id, steps_done, str(e), duration)
            error_msg = f"Process stopped because of an error: {str(e)}"
            conversation.add_turn(self.session_id, "assistant", error_msg, language)
            await self.tts.speak(error_msg)

    async def _execute_step_with_retry(self, step: dict, plan_id: str) -> tuple[str, str | None]:
        action = step["action_type"]
        params = step["parameters"]
        risk = safety.classify_risk_level(action, params)
        max_retries = config.MAX_RETRIES_PER_STEP
        
        last_error = None
        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                await self._dispatch(action, params)
                duration = int((time.time() - t0) * 1000)
                task_history.log_action(plan_id, step["step_id"], action, params, "success", duration_ms=duration)
                return ("success", None)
            except Exception as e:
                last_error = str(e)
                duration = int((time.time() - t0) * 1000)
                task_history.log_action(plan_id, step["step_id"], action, params, "failure", error_code=type(e).__name__, duration_ms=duration)
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
        return ("failure", last_error)

    async def _dispatch(self, action: str, params: dict):
        """Full dispatch table covering all allowed actions."""
        if action == "open_app":
            app_name = params.get("app_name") or params.get("app")
            if not app_name:
                raise KeyError("Missing 'app_name' or 'app' parameter for open_app action")
            app_control.open_app(app_name, params.get("args", []))
        elif action == "open_file":
            app_control.open_file(params["path"])
        elif action == "navigate_explorer":
            # Use PowerShell Shell.Application COM to navigate Explorer window
            nav_path = params["path"]
            ps_cmd = (
                "$shell = New-Object -ComObject Shell.Application; "
                "$win = $shell.Windows() | Where-Object {$_.Name -like '*Explorer*'} | Select-Object -First 1; "
                f"if ($win) {{ $win.Navigate('{nav_path}') }} "
                f"else {{ explorer.exe '{nav_path}' }}"
            )
            import subprocess
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                start_new_session=True
            )
        elif action == "close_app":
            app_name = params.get("app_name") or params.get("app")
            if not app_name:
                raise KeyError("Missing 'app_name' or 'app' parameter for close_app action")
            app_control.close_app(app_name, params.get("force", False))
        elif action == "open_browser":
            await browser.navigate(params.get("url") or "https://www.google.com")
        elif action == "navigate_url":
            url = params.get("url") or params.get("address")
            if not url:
                raise KeyError("Missing 'url' or 'address' parameter for navigate_url action")
            await browser.navigate(url)
        elif action == "browser_search":
            query = params.get("query") or params.get("text")
            if not query:
                raise KeyError("Missing 'query' or 'text' parameter for browser_search action")
            await browser.browser_search(query, params.get("engine", "google"))
        elif action == "click_element":
            await browser.click_element(params["selector"], params.get("selector_type", "css"))
        elif action == "read_element":
            self.last_read_result = await browser.read_element(params["selector"], params.get("selector_type", "css"))
        elif action == "get_element_attribute":
            self.last_read_result = await browser.get_element_attribute(params["selector"], params["attribute"])
        elif action == "fill_form":
            await browser.fill_form(params["selector"], params["text"], params.get("selector_type", "css"), params.get("enter", True))
        elif action == "download_file":
            await downloader.download_file(params.get("url"), params.get("selector"), params.get("destination", "~/Downloads"))
        elif action == "create_file":
            result = filesystem.create_file(params["path"], params.get("content", ""))
            await self.tts.speak("File created.")
        elif action == "read_file":
            self.last_read_result = filesystem.read_file(params["path"])
        elif action == "move_file":
            filesystem.move_file(params["source"], params["destination"])
        elif action == "copy_file":
            filesystem.copy_file(params["source"], params["destination"])
        elif action == "delete_file":
            if params.get("glob"):
                filesystem.delete_files_glob(params["path"], params["glob"])
            else:
                filesystem.delete_file(params["path"])
        elif action == "create_folder":
            result = filesystem.create_folder(params["path"])
            await self.tts.speak(f"Folder created.")
        elif action == "list_folder":
            filesystem.list_folder(params["path"], params.get("filter"))
        elif action == "type_text":
            keyboard_mouse.type_text(params["text"])
        elif action == "key_press":
            keys_param = params.get("keys") or params.get("key", "")
            modifiers = params.get("modifiers", [])
            # If keys_param is a string like "alt+d" or "ctrl+c", pass directly to keyboard.send
            if isinstance(keys_param, str):
                import keyboard as _kb
                _kb.send(keys_param)
            else:
                # Legacy list format
                keyboard_mouse.key_press(keys_param, modifiers if isinstance(modifiers, list) else [modifiers])
        elif action == "mouse_click":
            keyboard_mouse.mouse_click(params["x"], params["y"])
        elif action == "send_email":
            email_sender.send_email(params["to"], params["subject"], params["body"], params.get("attachments", []), params.get("cc", []))
        elif action == "run_command":
            import subprocess
            subprocess.Popen(params["command"], shell=True, start_new_session=True)
        elif action == "wait":
            await asyncio.sleep(params["seconds"])
        elif action == "save_custom_command":
            import json
            custom_commands.save_command(params["trigger_phrase"], json.dumps(params["plan"]))
        elif action == "list_custom_commands":
            cmds = custom_commands.list_commands()
            await self.tts.speak(f"You have {len(cmds)} shortcuts saved.")
        elif action == "delete_custom_command":
            custom_commands.delete_command(params["trigger_phrase"])
        elif action == "find_file":
            from amdea.execution.filesystem import fuzzy_find_file
            found = fuzzy_find_file(params.get("directory", "C:\\"), params["query"])
            if found:
                self.last_read_result = found
                await self.tts.speak(f"Found it: {pathlib.Path(found).name}")
            else:
                raise FileNotFoundError(f"Could not find any file matching '{params['query']}'")
        elif action == "respond_only":
            pass
        elif action == "clarify":
            await self.tts.speak(params["question"])
        else:
            raise ValueError(f"Unknown action: {action}")

    def _topological_sort(self, steps: list[dict]) -> list[dict]:
        """Kahn's algorithm for dependency resolution."""
        in_degree = {step["step_id"]: 0 for step in steps}
        adj = {step["step_id"]: [] for step in steps}
        step_map = {step["step_id"]: step for step in steps}
        
        for step in steps:
            for dep in step.get("depends_on", []):
                if dep in adj:
                    adj[dep].append(step["step_id"])
                    in_degree[step["step_id"]] += 1
                    
        queue = collections.deque([sid for sid, degree in in_degree.items() if degree == 0])
        sorted_steps = []
        
        while queue:
            u = queue.popleft()
            sorted_steps.append(step_map[u])
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
                    
        if len(sorted_steps) != len(steps):
            raise Exception("Circular dependency detected in plan.")
            
        return sorted_steps

    def cancel(self) -> None:
        self._cancelled = True
