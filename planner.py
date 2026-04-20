import os
import json
import logging
from openai import AsyncOpenAI
from typing import List, Dict, Any

logger = logging.getLogger("aura.core.planner")

# Task Planner API settings mirroring the LLM Engine structure
# Retrieve the simplified single GROQ_API_KEY line from .env
groq_api_key = os.environ.get("GROQ_API_KEY", "dummy-key")

# We seamlessly hook it directly into Groq Servers natively on startup
client = AsyncOpenAI(
    api_key=groq_api_key, 
    base_url="https://api.groq.com/openai/v1"
)
target_model = "llama-3.3-70b-versatile"

async def plan_tasks(command: str) -> List[Dict[str, Any]]:
    """
    Takes a complex command (e.g. "open notepad and write email for python internship"),
    analyzes it, and breaks it down into structured sequential JSON tasks.
    """
    logger.info(f"Task Planner: Analyzing complex command -> '{command}'")
    
    system_prompt = (
        "You are the Task Planner for AURA, an AI assistant. "
        "Your job is to break down complex multi-step commands into a structured list of sequential tasks. "
        "You MUST respond with VALID JSON. Return a single JSON object containing a key 'tasks' which is an array of task objects. "
        "Expected task object formats:\n"
        '{"task": "open_app", "app": "name of application"}\n'
        '{"task": "open_website", "url": "url"}\n'
        '{"task": "play_on_youtube", "query": "video or song name"}\n'
        '{"task": "get_date"}\n'
        '{"task": "get_time"}\n'
        '{"task": "set_volume", "level": 50}\n'
        '{"task": "generate_email", "topic": "topic description"}\n'
        '{"task": "write_text", "target": "where to write"}\n'
        '{"task": "system_control", "action": "volume_up/volume_down/mute"}\n'
        '{"task": "llm_query", "prompt": "question"}\n'
        '{"task": "create_file", "path": "file path", "content": "optional content"}\n'
        '{"task": "create_folder", "path": "folder path"}\n'
        '{"task": "delete_file", "path": "file path"}\n'
        '{"task": "delete_folder", "path": "folder path"}\n'
        '{"task": "open_folder", "path": "folder path"}\n'
        '{"task": "get_weather", "city": "city name"}\n'
        '{"task": "screenshot"}\n'
        '{"task": "open_camera"}\n'
        '{"task": "capture_image"}\n'
        '{"task": "search_file", "query": "filename to search"}\n'
        '{"task": "send_email", "to": "recipient", "subject": "subject", "body": "body text"}\n'
        '{"task": "set_reminder", "time": "5 pm", "task_desc": "what to remind"}\n'
        '{"task": "close_app", "app": "app name"}\n'
        "\nIMPORTANT DEPENDENCY RULES:\n"
        "1. If the user asks you to write something inside an application, you MUST explicitly output THREE sequential tasks: "
        "'open_app' -> 'generate_email' (or llm_query) -> 'write_text'.\n"
        "2. Do NOT skip 'write_text' if writing is implicitly requested!\n"
        "3. For file system operations, use the exact task types: create_file, create_folder, delete_file, delete_folder, open_folder.\n"
        "Example Output for 'Open notepad and write an email about a dog':\n"
        '{"tasks": [{"task": "open_app", "app": "notepad"}, {"task": "generate_email", "topic": "a dog"}, {"task": "write_text", "target": "notepad"}]}\n'
        "Example Output for 'Create a file test.txt and open folder D:\\':\n"
        '{"tasks": [{"task": "create_file", "path": "test.txt"}, {"task": "open_folder", "path": "D:\\\\"}]}\n'
    )
    
    try:
        # Prompt the LLM strictly enforcing JSON output
        response = await client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Command to plan: {command}"}
            ],
            # JSON mode guarantees the response is parsable JSON
            response_format={"type": "json_object"},
            temperature=0.1, # Low temperature ensures deterministic matching
            max_tokens=800
        )
        
        reply_json_str = response.choices[0].message.content.strip()
        logger.info(f"Task Planner generated raw JSON: {reply_json_str}")
        
        # Parse the output into Python dictionaries
        parsed_data = json.loads(reply_json_str)
        tasks_array = parsed_data.get("tasks", [])
        
        return tasks_array
        
    except Exception as e:
        logger.error(f"Task Planner Error: {e}")
        # Fallback to an error task mapping so the Execution Engine knows what failed
        return [{"task": "error", "message": f"Planner failed to decompose task: {str(e)}"}]
