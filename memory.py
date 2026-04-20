import json
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger("aura.core.memory")

# Secure file path relative to this script ensuring it remains within the backend folder
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory_store.json")

class AuraMemory:
    """
    Lightweight Memory System for AURA.
    - Persistent Preferences (Saved natively to JSON)
    - Ephemeral Short-term Conversation Context (In-Memory List for absolute minimum latency)
    """
    
    def __init__(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.preferences: Dict[str, Any] = self._load_preferences()
        
    def _load_preferences(self) -> dict:
        """Loads persistent user preferences from disk natively."""
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load memory file: {e}")
        return {}
        
    def _save_preferences(self):
        """Dumps preferences to disk securely."""
        try:
            with open(MEMORY_FILE, 'w') as f:
                json.dump(self.preferences, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to dump memory file securely: {e}")

    # ==========================
    # Short-term Context Logic
    # ==========================
    def add_context(self, role: str, content: str):
        """
        Appends an interaction block to the active conversation history.
        Caps at 10 to ensure we don't bleed out the LLM Token context windows on long sessions.
        """
        self.conversation_history.append({"role": role, "content": content})
        if len(self.conversation_history) > 10:
            self.conversation_history.pop(0)

    def get_context_string(self) -> str:
        """
        Returns recent messages as a clean block for the LLM injection prompt.
        """
        if not self.conversation_history:
            return ""
            
        history = "\n=== RECENT CONVERSATION CONTEXT ===\n"
        for msg in self.conversation_history:
            history += f"{msg['role'].capitalize()}: {msg['content']}\n"
        return history

    # ==========================
    # Long-term Profile Fact Logic
    # ==========================
    def remember_preference(self, key: str, value: str):
        """
        Stores user-specific facts permanently (e.g. 'name': 'Nisha').
        """
        self.preferences[key] = value
        self._save_preferences()
        logger.info(f"Memory explicitly updated: {key} = {value}")

    def get_all_preferences_string(self) -> str:
        """
        Structures the disk data securely for the LLM to understand known user facts.
        """
        if not self.preferences:
            return ""
        pref_str = "\n=== USER PREFERENCES & FACTS ===\n"
        for k, v in self.preferences.items():
            pref_str += f"- {k}: {v}\n"
        return pref_str

# Export a globally cached singleton instance to guarantee state retention across router calls
memory_system = AuraMemory()
