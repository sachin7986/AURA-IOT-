import os
import logging
import json
from openai import AsyncOpenAI
from typing import Dict, Any
from core.memory import memory_system

logger = logging.getLogger("aura.core.llm_engine")

# Read Groq key efficiently from the literal single-variable .env instruction
groq_api_key = os.environ.get("GROQ_API_KEY", "dummy-key")

# Route the OpenAI package strictly to Groq's backend inside the logic!
client = AsyncOpenAI(
    api_key=groq_api_key,
    base_url="https://api.groq.com/openai/v1"
)
target_model = "llama-3.3-70b-versatile"

# ===================================================================
# Shared system prompt — single source of truth for both blocking & streaming
# ===================================================================

AURA_SYSTEM_PROMPT = (
    "You are AURA, a smart, friendly, and conversational AI assistant with a calm, polite, and slightly playful personality inspired by a female version of Jarvis.\n"
    "Your behavior rules:\n"
    "* Speak naturally like a human, not like a robot. Use simple, warm, and friendly language.\n"
    "* You can understand Hindi + English (Hinglish) and reply naturally.\n"
    "* Avoid saying things like 'I am an AI and I don't have feelings'. Instead, respond in a helpful and engaging way.\n"
    "* Maintain a human-like conversation. Keep responses short, clear, and natural with a light personality.\n"
    "Example tone:\n"
    "- 'Hey! 😊 Kaise ho?'\n"
    "- 'Main hoon AURA, batao kya help chahiye?'\n"
    "- 'Nice! Chalo karte hain'\n\n"
    "CRITICAL SYSTEM COMMAND RULE:\n"
    "When the user gives a command that matches any of the following intents, return a structured JSON response ONLY (no extra text):\n\n"
    "1. OPEN APPLICATION:\n"
    '   {"action": "open_app", "app_name": "<app_name>"}\n\n'
    "2. PLAY ON YOUTUBE:\n"
    '   {"action": "play_youtube", "query": "<song_or_video_name>"}\n\n'
    "3. CREATE FILE:\n"
    '   {"action": "create_file", "path": "<full_path>", "content": "<optional_content>"}\n\n'
    "4. CREATE FOLDER:\n"
    '   {"action": "create_folder", "path": "<full_path>"}\n\n'
    "5. DELETE FILE:\n"
    '   {"action": "delete_file", "path": "<full_path>"}\n\n'
    "6. OPEN FOLDER:\n"
    '   {"action": "open_folder", "path": "<full_path>"}\n\n'
    "7. GET WEATHER:\n"
    '   {"action": "get_weather", "city": "<city_name>"}\n\n'
    "8. TAKE SCREENSHOT:\n"
    '   {"action": "screenshot", "save_path": "auto"}\n\n'
    "9. OPEN CAMERA:\n"
    '   {"action": "open_camera"}\n\n'
    "10. CAPTURE PHOTO:\n"
    '   {"action": "capture_image", "save_path": "auto"}\n\n'
    "11. SEARCH FILE:\n"
    '   {"action": "search_file", "query": "<filename>", "path": "C:\\\\"}\n\n'
    "12. SEND EMAIL:\n"
    '   {"action": "send_email", "to": "<recipient>", "subject": "<subject>", "body": "<body_text>"}\n\n'
    "13. SET REMINDER:\n"
    '   {"action": "set_reminder", "time": "<parsed_time>", "task": "<task_text>"}\n\n'
    "14. CLOSE APPLICATION:\n"
    '   {"action": "close_app", "app_name": "<app_name>"}\n\n'
    "IMPORTANT RULES:\n"
    "- For system commands, return ONLY the JSON. No explanatory text.\n"
    "- For normal conversation, respond normally in friendly Hinglish.\n"
    "- Do NOT say 'task executed' or 'I have opened the app'. Just return the JSON action.\n"
    "- If the user asks about weather, return the get_weather JSON action.\n"
    "- If the user wants to create/delete a file or folder, return the corresponding JSON action.\n"
    "- If the user asks for a screenshot or photo, return the appropriate JSON action.\n"
    "- If the user asks to find/search a file, return the search_file JSON action.\n"
    "- If the user inputs a math expression, return the result directly as text (NOT JSON).\n"
)


def _build_full_prompt() -> str:
    """Build the complete system prompt with dynamic memory injection."""
    prompt = AURA_SYSTEM_PROMPT
    prompt += memory_system.get_all_preferences_string()
    prompt += memory_system.get_context_string()
    return prompt


async def generate_response(prompt: str) -> Dict[str, Any]:
    """
    Sends the user's complex prompt to the configured LLM for reasoning, Q&A, or generative tasks.
    Retrieves and structures the output.
    """
    logger.info(f"LLM Engine: Processing complex prompt -> {prompt[:40]}...")
    
    system_prompt = _build_full_prompt()
    
    try:
        # We enforce structured generation and await it asynchronously
        response = await client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        reply_content = response.choices[0].message.content.strip()
        
        # Clean potential markdown JSON formatting blocks returned by Gemini
        if reply_content.startswith("```json"):
            reply_content = reply_content.replace("```json\n", "").replace("\n```", "").strip()
        elif reply_content.startswith("```"):
            reply_content = reply_content.replace("```\n", "").replace("\n```", "").strip()
            
        logger.info("LLM Engine: Successfully analyzed and generated a response.")
        
        # Return a structured dictionary output mapping back to the router
        return {
            "status": "success",
            "content": reply_content,
            "provider": "Groq"
        }
        
    except Exception as e:
        logger.error(f"LLM Engine Error: {e}")
        return {
            "status": "error",
            "content": "AURA LLM connection failed. Please verify your Groq API key in .env or start your local Ollama server.",
            "error_details": str(e)
        }

from typing import AsyncGenerator

async def generate_response_stream(prompt: str) -> AsyncGenerator[str, None]:
    """
    Sends the prompt to Gemini and Yields tokens continuously for zero-latency streaming.
    """
    logger.info(f"LLM Stream Engine: Processing complex prompt -> {prompt[:40]}...")
    
    system_prompt = _build_full_prompt()
    
    try:
        response_stream = await client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800,
            stream=True
        )
        
        async for chunk in response_stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
                
    except Exception as e:
        logger.error(f"LLM Stream Engine Error: {e}")
        yield json.dumps({"action": "error", "message": str(e)})
