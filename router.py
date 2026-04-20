import logging
import json
import re
from datetime import datetime
from core.fast_engine import open_app_system, close_app_system, open_website, play_on_youtube, control_system
from core.llm_engine import generate_response, generate_response_stream
from core.planner import plan_tasks
from core.executor import execute_tasks
from core.memory import memory_system
from core.system_actions import (
    execute_system_action, get_weather,
    open_folder, create_file, create_folder, delete_file, delete_folder,
    take_screenshot, open_camera, capture_image,
    search_file, calculate, is_math_expression,
    send_email_action, parse_reminder_time
)
from core.command_parser import parse_command

logger = logging.getLogger("aura.core.router")

# ===================================================================
# Helper: detect if text is a system command rather than a conversation
# ===================================================================
def _is_play_youtube(cmd: str) -> bool:
    """Check if the command is explicitly asking to play something on YouTube."""
    return ("play" in cmd and "youtube" in cmd) or cmd.startswith("play ")

def _extract_youtube_query(cmd: str) -> str:
    """Pull the song/video name out of the command string."""
    cmd = cmd.lower().strip()
    # Remove common phrasing
    for phrase in ["on youtube", "from youtube", "in youtube", "youtube"]:
        cmd = cmd.replace(phrase, "")
    for phrase in ["play", "search"]:
        if cmd.startswith(phrase):
            cmd = cmd[len(phrase):]
    return cmd.strip()

def _is_weather_query(cmd: str) -> bool:
    """Check if the command is asking about weather."""
    return any(kw in cmd for kw in ["weather", "mausam", "mosam"])

def _extract_weather_city(cmd: str) -> str:
    """Extract the city name from a weather query."""
    import re
    match = re.search(r'(?:weather|mausam|mosam)\s*(?:in|of|at|for|ka)?\s+(.+)', cmd)
    if match:
        return match.group(1).strip()
    return "auto"  # wttr.in auto-detects location

def _is_file_operation(cmd: str) -> bool:
    """Check if the command is a file system operation."""
    file_keywords = ["create file", "make file", "banao file",
                     "create folder", "make folder", "banao folder",
                     "create directory", "make directory",
                     "delete file", "remove file", "hatao file",
                     "delete folder", "remove folder", "hatao folder",
                     "open folder", "open directory", "open dir"]
    return any(kw in cmd for kw in file_keywords)

def _is_screenshot_command(cmd: str) -> bool:
    """Check if the command is asking for a screenshot."""
    return any(kw in cmd for kw in ["screenshot", "screen shot", "capture screen", "screen capture"])

def _is_camera_command(cmd: str) -> bool:
    """Check if the command involves the camera."""
    return any(kw in cmd for kw in ["capture photo", "take photo", "take picture",
                                     "capture image", "take selfie", "open camera",
                                     "photo lelo", "photo khicho"])

def _is_search_file_command(cmd: str) -> bool:
    """Check if the command is searching for files."""
    return any(kw in cmd for kw in ["find file", "search file", "locate file",
                                     "dhundho file", "khojo file",
                                     "find files", "search files"])

def _is_email_command(cmd: str) -> bool:
    """Check if the command is about sending email."""
    return bool(re.search(r'(?:send|write)\s+(?:an?\s+)?(?:email|mail)', cmd))

def _is_reminder_command(cmd: str) -> bool:
    """Check if the command is setting a reminder."""
    return any(kw in cmd for kw in ["remind me", "set reminder", "reminder", "yaad dila"])


async def route_command(command: str) -> dict:
    """
    Decides whether the command should go to the Fast Engine, LLM Engine, or Task Planner.
    Returns a dict with the engine invoked and the generated response.
    """
    logger.info(f"Routing command: '{command}'")
    command_lower = command.lower().strip()
    
    # =========================================================
    # 0. Memory Engine Routing
    # =========================================================
    if command_lower.startswith("my name is "):
        name = command[11:].strip()
        memory_system.remember_preference("name", name)
        return {"engine": "memory", "response": f"Got it, pleased to meet you, {name}!"}
        
    elif command_lower.startswith("remember that ") or command_lower.startswith("remember to "):
        fact = command[12:].strip()
        memory_system.remember_preference(f"fact_{len(memory_system.preferences)}", fact)
        return {"engine": "memory", "response": "I've securely logged that into my long-term memory."}
    
    # =========================================================
    # 1. Fast Engine Routing (Simple / Deterministic)
    # =========================================================
    if command_lower in ["ping", "hello", "hi"]:
        logger.info("Routed to: Fast Engine")
        return {"engine": "fast", "response": "Hello! AURA is online and ready."}

    # --- IoT Light Control ---
    elif any(kw in command_lower for kw in ["light on", "turn on light", "turn on the light"]):
        logger.info("Routed to: Fast Engine (IoT Light ON)")
        from core.iot.light_controller import turn_on_light
        return {"engine": "fast", "response": turn_on_light()}
        
    elif any(kw in command_lower for kw in ["light off", "turn off light", "turn off the light"]):
        logger.info("Routed to: Fast Engine (IoT Light OFF)")
        from core.iot.light_controller import turn_off_light
        return {"engine": "fast", "response": turn_off_light()}

    # --- IoT Fan/AC/TV Controls (Dummy for missing hardware) ---
    elif any(kw in command_lower for kw in ["fan on", "turn on fan", "fan off", "turn off fan", "turn on the fan", "turn off the fan"]):
        logger.info("Routed to: Fast Engine (IoT Fan)")
        return {"engine": "fast", "response": "Fan is not connected"}
    
    elif any(kw in command_lower for kw in ["ac on", "turn on ac", "ac off", "turn off ac", "turn on the ac", "turn off the ac"]):
        logger.info("Routed to: Fast Engine (IoT AC)")
        return {"engine": "fast", "response": "AC is not connected"}

    elif any(kw in command_lower for kw in ["tv on", "turn on tv", "tv off", "turn off tv", "turn on the tv", "turn off the tv"]):
        logger.info("Routed to: Fast Engine (IoT TV)")
        return {"engine": "fast", "response": "TV is not connected"}
    
    # =========================================================
    # 1b. Weather Queries (returns natural text, NOT JSON)
    # =========================================================
    elif _is_weather_query(command_lower):
        logger.info("Routed to: Weather Engine")
        city = _extract_weather_city(command_lower)
        result = get_weather(city)
        return {"engine": "weather", "response": result}
    
    # --- System Actions (date, time, battery, brightness) ---
    elif any(kw in command_lower for kw in ["time", "date", "today", "battery", "brightness", "samay", "aaj"]):
        logger.info("Routed to: System Actions")
        result = execute_system_action(command_lower)
        return {"engine": "system", "response": result}

    # =========================================================
    # 1c. File System Operations (create/delete file/folder, open folder)
    # =========================================================
    elif _is_file_operation(command_lower):
        logger.info("Routed to: File System Engine")
        result = execute_system_action(command_lower)
        return {"engine": "filesystem", "response": result}

    # =========================================================
    # 1d. Screenshot Capture
    # =========================================================
    elif _is_screenshot_command(command_lower):
        logger.info("Routed to: Screenshot Engine")
        result = take_screenshot()
        return {"engine": "screenshot", "response": result}

    # =========================================================
    # 1e. Camera (open + capture photo)
    # =========================================================
    elif _is_camera_command(command_lower):
        logger.info("Routed to: Camera Engine")
        if any(kw in command_lower for kw in ["capture photo", "take photo", "take picture", "capture image", "take selfie", "photo lelo", "photo khicho"]):
            result = capture_image()
        else:
            result = open_camera()
        return {"engine": "camera", "response": result}

    # =========================================================
    # 1f. File Search
    # =========================================================
    elif _is_search_file_command(command_lower):
        logger.info("Routed to: File Search Engine")
        match = re.search(r'(?:find|search|locate|dhundho|khojo)\s+(?:files?)?\s*(.+)', command_lower)
        query = match.group(1).strip() if match else command_lower
        result = search_file(query)
        return {"engine": "search", "response": result}

    # =========================================================
    # 1g. Calculator (math expressions)
    # =========================================================
    elif is_math_expression(command_lower):
        logger.info("Routed to: Calculator Engine")
        result = calculate(command_lower)
        return {"engine": "calculator", "response": result}

    # =========================================================
    # 1h. Email Sending
    # =========================================================
    elif _is_email_command(command_lower):
        logger.info("Routed to: Email Engine")
        result = execute_system_action(command_lower)
        return {"engine": "email", "response": result}

    # =========================================================
    # 1i. Reminders / Task Scheduler
    # =========================================================
    elif _is_reminder_command(command_lower):
        logger.info("Routed to: Reminder Engine")
        result = execute_system_action(command_lower)
        return {"engine": "reminder", "response": result}

    # =========================================================
    # 2. YouTube Play (check BEFORE "and" splitter)
    # =========================================================
    elif _is_play_youtube(command_lower):
        logger.info("Routed to: Fast Engine (YouTube)")
        query = _extract_youtube_query(command_lower)
        result = play_on_youtube(query)
        return {"engine": "fast", "response": f"Playing '{query}' on YouTube for you!"}
        
    # =========================================================
    # 3. Multi-command parser (local, no LLM needed)
    # =========================================================
    parsed_steps = parse_command(command)
    if len(parsed_steps) > 0:
        if len(parsed_steps) == 1 and parsed_steps[0]["action"] == "close_app":
            result = close_app_system(parsed_steps[0]["target"])
            return {"engine": "fast", "response": result}
        elif len(parsed_steps) == 1 and parsed_steps[0]["action"] == "open_app":
            result = open_app_system(parsed_steps[0]["target"])
            return {"engine": "fast", "response": result}
        elif len(parsed_steps) == 1:
            # Single file op (create_file, delete_file, etc.)
            step = parsed_steps[0]
            result = _execute_parser_step(step)
            return {"engine": "filesystem", "response": result}
        else:
            # Multi-command: execute all steps
            logger.info(f"Command Parser produced {len(parsed_steps)} steps")
            results = []
            for step in parsed_steps:
                results.append(_execute_parser_step(step))
            
            summary = " | ".join(results)
            return {
                "engine": "executor",
                "planner_output": parsed_steps,
                "response": summary
            }
    
    # Fallback: if "and"/"then" present but parser couldn't handle it, use LLM planner
    elif " and " in command_lower or " then " in command_lower:
        logger.info("Routed to: LLM Task Planner (parser couldn't handle)")
        plan = await plan_tasks(command)
        exec_results = await execute_tasks(plan)
        return {
            "engine": "executor",
            "planner_output": plan,
            "response": exec_results
        }
        
    # =========================================================
    # 4. Direct App/Website Opening
    # =========================================================
    elif command_lower.startswith("open ") or command_lower.startswith("launch "):
        logger.info("Routed to: Fast Engine (App/Website)")
        target = command_lower.replace("open ", "").replace("launch ", "").strip()
        
        if "." in target and " " not in target:
            result = open_website(target)
        else:
            result = open_app_system(target)
            
        return {"engine": "fast", "response": result}
    
    # =========================================================
    # 4b. Direct App Closing
    # =========================================================
    elif any(command_lower.startswith(v + " ") for v in ["close", "kill", "exit", "quit", "terminate", "band"]):
        logger.info("Routed to: Fast Engine (Close App)")
        for v in ["close", "kill", "exit", "quit", "terminate", "band"]:
            if command_lower.startswith(v + " "):
                target = command_lower[len(v):].strip()
                break
        result = close_app_system(target)
        return {"engine": "fast", "response": result}
        
    # =========================================================
    # 5. System Controls (volume, mute, shutdown)
    # =========================================================
    elif any(kw in command_lower for kw in ["volume", "mute", "unmute", "shutdown", "restart"]):
        logger.info("Routed to: System Actions (Control)")
        result = execute_system_action(command_lower)
        return {"engine": "system", "response": result}
        
    # =========================================================
    # 6. LLM Engine (Conversation + Intent Parsing Fallback)
    # =========================================================
    else:
        logger.info("Routed to: LLM Engine (Intent Parsing & Conversation)")
        llm_result = await generate_response(command)
        response_text = llm_result["content"]
        
        # Check if the LLM returned a JSON action instead of conversation
        if response_text.strip().startswith("{") and '"action"' in response_text:
            try:
                data = json.loads(response_text.strip())
                action = data.get("action", "")
                
                if action == "open_app":
                    target = data.get("app_name", "")
                    logger.info(f"LLM extracted OS Command: open_app -> {target}")
                    if "." in target and " " not in target:
                        open_website(target)
                    else:
                        open_app_system(target)
                    return {"engine": "llm -> fast", "response": f"Opening {target} for you now!"}
                    
                elif action == "play_youtube":
                    query = data.get("query", "")
                    logger.info(f"LLM extracted OS Command: play_youtube -> {query}")
                    play_on_youtube(query)
                    return {"engine": "llm -> fast", "response": f"Playing '{query}' on YouTube for you!"}
                
                elif action == "create_file":
                    path = data.get("path", "")
                    content = data.get("content", "")
                    result = create_file(path, content)
                    return {"engine": "llm -> filesystem", "response": result}
                
                elif action == "create_folder":
                    path = data.get("path", "")
                    result = create_folder(path)
                    return {"engine": "llm -> filesystem", "response": result}
                
                elif action == "delete_file":
                    path = data.get("path", "")
                    result = delete_file(path)
                    return {"engine": "llm -> filesystem", "response": result}
                
                elif action == "open_folder":
                    path = data.get("path", "")
                    result = open_folder(path)
                    return {"engine": "llm -> filesystem", "response": result}
                
                elif action == "get_weather":
                    city = data.get("city", "auto")
                    result = get_weather(city)
                    return {"engine": "llm -> weather", "response": result}
                
                elif action == "screenshot":
                    result = take_screenshot(data.get("save_path", "auto"))
                    return {"engine": "llm -> screenshot", "response": result}
                
                elif action == "open_camera":
                    result = open_camera()
                    return {"engine": "llm -> camera", "response": result}
                
                elif action == "capture_image":
                    result = capture_image(data.get("save_path", "auto"))
                    return {"engine": "llm -> camera", "response": result}
                
                elif action == "search_file":
                    query = data.get("query", "")
                    path = data.get("path", None)
                    result = search_file(query, path)
                    return {"engine": "llm -> search", "response": result}
                
                elif action == "send_email":
                    result = send_email_action(
                        to=data.get("to", ""),
                        subject=data.get("subject", ""),
                        body=data.get("body", "")
                    )
                    return {"engine": "llm -> email", "response": result}
                
                elif action == "set_reminder":
                    task = data.get("task", "")
                    time_val = data.get("time", "")
                    parsed = parse_reminder_time(time_val)
                    if parsed == "invalid":
                        return {"engine": "llm -> reminder", "response": f"Could not parse time '{time_val}'."}
                    return {"engine": "llm -> reminder", "response": f"Reminder set: '{task}' at {parsed}."}
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON: {e}")
        
        return {"engine": "llm", "response": response_text}


def _execute_parser_step(step: dict) -> str:
    """Execute a single step from the command parser."""
    action = step.get("action", "")
    target = step.get("target", "")
    
    if action == "open_app":
        return open_app_system(target)
    elif action == "close_app":
        return close_app_system(target)
    elif action == "open_website":
        return open_website(target)
    elif action == "play_youtube":
        return play_on_youtube(target)
    elif action == "open_folder":
        return open_folder(target)
    elif action == "create_file":
        return create_file(target)
    elif action == "create_folder":
        return create_folder(target)
    elif action == "delete_file":
        return delete_file(target)
    elif action == "delete_folder":
        return delete_folder(target)
    elif action == "screenshot":
        return take_screenshot()
    elif action == "capture_image":
        return capture_image()
    elif action == "search_file":
        return search_file(target)
    else:
        return f"Unknown action: {action}"


# ===================================================================
# STREAMING VERSION (for WebSocket real-time delivery)
# ===================================================================

async def route_command_stream(command: str):
    """
    Streaming version of route_command.
    Yields chunks as they compute for zero-latency WebSocket delivery.
    """
    logger.info(f"Streaming Route: '{command}'")
    command_lower = command.lower().strip()

    # =========================================================
    # 0. Memory Engine Routing
    # =========================================================
    if command_lower.startswith("my name is "):
        name = command[11:].strip()
        memory_system.remember_preference("name", name)
        yield json.dumps({"engine": "memory"})
        yield f"Got it! Nice to meet you, {name}! I'll remember that."
        return

    elif command_lower.startswith("remember that ") or command_lower.startswith("remember to "):
        fact = command[12:].strip()
        memory_system.remember_preference(f"fact_{len(memory_system.preferences)}", fact)
        yield json.dumps({"engine": "memory"})
        yield "Done! I've saved that to my long-term memory."
        return

    # =========================================================
    # 1. Fast Engine Short-Circuits
    # =========================================================
    if command_lower in ["ping", "hello", "hi"]:
        yield json.dumps({"engine": "fast"})
        yield "Hey! Main hoon AURA, batao kya help chahiye?"
        return

    # --- IoT Light Control ---
    elif any(kw in command_lower for kw in ["light on", "turn on light", "turn on the light"]):
        yield json.dumps({"engine": "fast"})
        from core.iot.light_controller import turn_on_light
        yield turn_on_light()
        return
        
    elif any(kw in command_lower for kw in ["light off", "turn off light", "turn off the light"]):
        yield json.dumps({"engine": "fast"})
        from core.iot.light_controller import turn_off_light
        yield turn_off_light()
        return

    # --- IoT Fan/AC/TV Controls (Dummy for missing hardware) ---
    elif any(kw in command_lower for kw in ["fan on", "turn on fan", "fan off", "turn off fan", "turn on the fan", "turn off the fan"]):
        yield json.dumps({"engine": "fast"})
        yield "Fan is not connected"
        return

    elif any(kw in command_lower for kw in ["ac on", "turn on ac", "ac off", "turn off ac", "turn on the ac", "turn off the ac"]):
        yield json.dumps({"engine": "fast"})
        yield "AC is not connected"
        return

    elif any(kw in command_lower for kw in ["tv on", "turn on tv", "tv off", "turn off tv", "turn on the tv", "turn off the tv"]):
        yield json.dumps({"engine": "fast"})
        yield "TV is not connected"
        return

    # =========================================================
    # 1b. Weather Queries (natural text response)
    # =========================================================
    elif _is_weather_query(command_lower):
        yield json.dumps({"engine": "weather"})
        city = _extract_weather_city(command_lower)
        result = get_weather(city)
        yield result
        return

    # --- System Actions (date, time, battery, brightness) ---
    elif any(kw in command_lower for kw in ["time", "date", "today", "battery", "brightness", "samay", "aaj"]):
        yield json.dumps({"engine": "system"})
        yield execute_system_action(command_lower)
        return

    # =========================================================
    # 1c. File System Operations
    # =========================================================
    elif _is_file_operation(command_lower):
        yield json.dumps({"engine": "filesystem"})
        result = execute_system_action(command_lower)
        yield result
        return

    # =========================================================
    # 1d. Screenshot Capture
    # =========================================================
    elif _is_screenshot_command(command_lower):
        yield json.dumps({"engine": "screenshot"})
        result = take_screenshot()
        yield result
        return

    # =========================================================
    # 1e. Camera
    # =========================================================
    elif _is_camera_command(command_lower):
        yield json.dumps({"engine": "camera"})
        if any(kw in command_lower for kw in ["capture photo", "take photo", "take picture", "capture image", "take selfie", "photo lelo", "photo khicho"]):
            result = capture_image()
        else:
            result = open_camera()
        yield result
        return

    # =========================================================
    # 1f. File Search
    # =========================================================
    elif _is_search_file_command(command_lower):
        yield json.dumps({"engine": "search"})
        match = re.search(r'(?:find|search|locate|dhundho|khojo)\s+(?:files?)?\s*(.+)', command_lower)
        query = match.group(1).strip() if match else command_lower
        result = search_file(query)
        yield result
        return

    # =========================================================
    # 1g. Calculator
    # =========================================================
    elif is_math_expression(command_lower):
        yield json.dumps({"engine": "calculator"})
        result = calculate(command_lower)
        yield result
        return

    # =========================================================
    # 1h. Email
    # =========================================================
    elif _is_email_command(command_lower):
        yield json.dumps({"engine": "email"})
        result = execute_system_action(command_lower)
        yield result
        return

    # =========================================================
    # 1i. Reminders
    # =========================================================
    elif _is_reminder_command(command_lower):
        yield json.dumps({"engine": "reminder"})
        result = execute_system_action(command_lower)
        yield result
        return

    # =========================================================
    # 2. YouTube Play (check BEFORE "and" splitter)
    # =========================================================
    elif _is_play_youtube(command_lower):
        yield json.dumps({"engine": "fast"})
        query = _extract_youtube_query(command_lower)
        play_on_youtube(query)
        yield f"Playing '{query}' on YouTube for you!"
        return

    # =========================================================
    # 3. Multi-command parser (local, no LLM needed)
    # =========================================================
    parsed_steps = parse_command(command)
    if len(parsed_steps) > 0:
        yield json.dumps({"engine": "executor"})
        results = []
        for step in parsed_steps:
            results.append(_execute_parser_step(step))
        summary = " | ".join(results)
        yield summary
        return

    # Fallback: if "and"/"then" present but parser couldn't handle it, use LLM planner
    elif " and " in command_lower or " then " in command_lower:
        yield json.dumps({"engine": "executor"})
        plan = await plan_tasks(command)
        yield json.dumps({"tasks_buffer": plan})
        await execute_tasks(plan)
        yield f"Done! I've completed {len(plan)} tasks for you."
        return

    # =========================================================
    # 4. Direct App/Website Opening
    # =========================================================
    elif command_lower.startswith("open ") or command_lower.startswith("launch "):
        yield json.dumps({"engine": "fast"})
        target = command_lower.replace("open ", "").replace("launch ", "").strip()
        if "." in target and " " not in target:
            open_website(target)
        else:
            open_app_system(target)
        yield f"Opening {target} for you!"
        return

    # =========================================================
    # 4b. Direct App Closing
    # =========================================================
    elif any(command_lower.startswith(v + " ") for v in ["close", "kill", "exit", "quit", "terminate", "band"]):
        yield json.dumps({"engine": "fast"})
        for v in ["close", "kill", "exit", "quit", "terminate", "band"]:
            if command_lower.startswith(v + " "):
                target = command_lower[len(v):].strip()
                break
        result = close_app_system(target)
        yield result
        return

    # =========================================================
    # 5. System Controls (volume, mute)
    # =========================================================
    elif any(kw in command_lower for kw in ["volume", "mute", "unmute", "shutdown", "restart"]):
        yield json.dumps({"engine": "system"})
        yield execute_system_action(command_lower)
        return

    # =========================================================
    # 6. LLM Streaming (conversational fallback)
    # =========================================================
    yield json.dumps({"engine": "llm"})

    buffer = ""
    is_json_building = False

    async for token in generate_response_stream(command):
        buffer += token

        # Detect if the LLM is building a JSON action block
        if buffer.strip().startswith("{") and not is_json_building:
            is_json_building = True

        if is_json_building:
            continue  # Accumulate until JSON is complete
        else:
            yield token  # Stream conversational text to UI

    # If the LLM built a JSON action, execute it
    if is_json_building:
        clean = buffer.strip()
        # Strip markdown code fences if present
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(clean)
            action = data.get("action", "")

            if action == "open_app":
                target = data.get("app_name", "")
                open_app_system(target)
                yield f"Opening {target} for you!"
            elif action == "play_youtube":
                query = data.get("query", "")
                play_on_youtube(query)
                yield f"Playing '{query}' on YouTube for you!"
            elif action == "create_file":
                path = data.get("path", "")
                content = data.get("content", "")
                result = create_file(path, content)
                yield result
            elif action == "create_folder":
                path = data.get("path", "")
                result = create_folder(path)
                yield result
            elif action == "delete_file":
                path = data.get("path", "")
                result = delete_file(path)
                yield result
            elif action == "open_folder":
                path = data.get("path", "")
                result = open_folder(path)
                yield result
            elif action == "get_weather":
                city = data.get("city", "auto")
                result = get_weather(city)
                yield result
            elif action == "screenshot":
                result = take_screenshot(data.get("save_path", "auto"))
                yield result
            elif action == "open_camera":
                result = open_camera()
                yield result
            elif action == "capture_image":
                result = capture_image(data.get("save_path", "auto"))
                yield result
            elif action == "search_file":
                query = data.get("query", "")
                path = data.get("path", None)
                result = search_file(query, path)
                yield result
            elif action == "send_email":
                result = send_email_action(
                    to=data.get("to", ""),
                    subject=data.get("subject", ""),
                    body=data.get("body", "")
                )
                yield result
            elif action == "set_reminder":
                task = data.get("task", "")
                time_val = data.get("time", "")
                parsed = parse_reminder_time(time_val)
                if parsed == "invalid":
                    yield f"Could not parse time '{time_val}'."
                else:
                    yield f"Reminder set: '{task}' at {parsed}."
            elif action:
                yield f"Executed action: {action}"
            else:
                yield "Sorry, I couldn't process that command properly. Try again!"
        except json.JSONDecodeError:
            logger.error(f"Could not parse LLM JSON output: {clean[:100]}")
            yield "Sorry, I had trouble understanding that command. Could you try again?"
