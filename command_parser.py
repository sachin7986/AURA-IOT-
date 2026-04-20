"""
command_parser.py — Parses natural language into structured action steps.
Handles multi-commands separated by "and" / "then" / "aur" without needing the LLM.
"""
import re
import logging

logger = logging.getLogger("aura.core.command_parser")

# Known action verbs AURA understands
OPEN_VERBS = ["open", "launch", "start", "run", "chalu"]
CLOSE_VERBS = ["close", "kill", "exit", "quit", "stop", "terminate", "band"]
PLAY_VERBS = ["play"]
CREATE_VERBS = ["create", "make", "banao"]
DELETE_VERBS = ["delete", "remove", "hatao"]
SEARCH_VERBS = ["find", "search", "locate", "dhundho", "khojo"]
SCREENSHOT_PHRASES = ["take screenshot", "capture screen", "screen capture", "screenshot"]
CAPTURE_PHRASES = ["capture photo", "take photo", "take picture", "capture image", "take selfie"]


def parse_command(input_text: str) -> list:
    """
    Takes a raw user input and returns a list of structured step dicts.
    
    Example:
        "open notepad and close chrome" 
        -> [{"action": "open_app", "target": "notepad"}, {"action": "close_app", "target": "chrome"}]
    
    Returns empty list if no structured commands detected (falls through to LLM).
    """
    text = input_text.strip()
    text_lower = text.lower()
    
    # Quick check: does this even look like a multi-command or action command?
    all_verbs = OPEN_VERBS + CLOSE_VERBS + PLAY_VERBS + CREATE_VERBS + DELETE_VERBS + SEARCH_VERBS
    has_action_verb = any(v in text_lower for v in all_verbs)
    has_special_phrase = any(p in text_lower for p in SCREENSHOT_PHRASES + CAPTURE_PHRASES)
    if not has_action_verb and not has_special_phrase:
        return []
    
    # Split on "and" / "then" / "aur" / "," keeping order
    parts = re.split(r'\s+and\s+|\s+then\s+|\s+aur\s+|,\s*', text_lower)
    parts = [p.strip() for p in parts if p.strip()]
    
    steps = []
    for part in parts:
        step = _parse_single(part)
        if step:
            steps.append(step)
    
    logger.info(f"Command Parser: '{input_text}' -> {steps}")
    return steps


def _parse_single(phrase: str) -> dict:
    """
    Parse a single sub-command phrase into a structured step dict.
    Returns None if unrecognized.
    """
    phrase = phrase.strip()
    
    # --- CLOSE commands ---
    for verb in CLOSE_VERBS:
        if phrase.startswith(verb + " "):
            target = phrase[len(verb):].strip()
            if target:
                return {"action": "close_app", "target": target}
    
    # --- CREATE commands ---
    for verb in CREATE_VERBS:
        if phrase.startswith(verb + " "):
            rest = phrase[len(verb):].strip()
            
            # "create file <path>"
            file_match = re.match(r'(?:a\s+)?file\s+(.+)', rest)
            if file_match:
                return {"action": "create_file", "target": file_match.group(1).strip().strip('"').strip("'")}
            
            # "create folder <path>"
            folder_match = re.match(r'(?:a\s+)?(?:folder|directory|dir)\s+(.+)', rest)
            if folder_match:
                return {"action": "create_folder", "target": folder_match.group(1).strip().strip('"').strip("'")}
    
    # --- DELETE commands ---
    for verb in DELETE_VERBS:
        if phrase.startswith(verb + " "):
            rest = phrase[len(verb):].strip()
            
            # "delete file <path>"
            file_match = re.match(r'(?:the\s+)?file\s+(.+)', rest)
            if file_match:
                return {"action": "delete_file", "target": file_match.group(1).strip().strip('"').strip("'")}
            
            # "delete folder <path>"
            folder_match = re.match(r'(?:the\s+)?(?:folder|directory|dir)\s+(.+)', rest)
            if folder_match:
                return {"action": "delete_folder", "target": folder_match.group(1).strip().strip('"').strip("'")}
    
    # --- OPEN commands ---
    for verb in OPEN_VERBS:
        if phrase.startswith(verb + " "):
            target = phrase[len(verb):].strip()
            if target:
                # "open folder <path>"
                folder_match = re.match(r'(?:the\s+)?(?:folder|directory|dir)\s+(.+)', target)
                if folder_match:
                    return {"action": "open_folder", "target": folder_match.group(1).strip().strip('"').strip("'")}
                
                # Check if it's a website
                if "." in target and " " not in target:
                    return {"action": "open_website", "target": target}
                return {"action": "open_app", "target": target}
    
    # --- PLAY commands ---
    for verb in PLAY_VERBS:
        if phrase.startswith(verb + " "):
            query = phrase[len(verb):].strip()
            # Remove "on youtube" / "from youtube"
            for suffix in ["on youtube", "from youtube", "in youtube"]:
                query = query.replace(suffix, "").strip()
            if query:
                return {"action": "play_youtube", "target": query}
    
    # --- SCREENSHOT commands ---
    for sp in SCREENSHOT_PHRASES:
        if phrase.startswith(sp) or phrase == sp:
            return {"action": "screenshot", "target": "auto"}
    
    # --- CAPTURE PHOTO commands ---
    for cp in CAPTURE_PHRASES:
        if phrase.startswith(cp) or phrase == cp:
            return {"action": "capture_image", "target": "auto"}
    
    # --- FILE SEARCH commands ---
    for verb in SEARCH_VERBS:
        if phrase.startswith(verb + " "):
            rest = phrase[len(verb):].strip()
            # Remove "file" / "files" prefix
            rest = re.sub(r'^(?:file|files)\s+', '', rest).strip()
            if rest:
                return {"action": "search_file", "target": rest}
    
    return None
