import speech_recognition as sr
import edge_tts
import asyncio
import pygame
import os
import logging
import tempfile
import re

logger = logging.getLogger("aura.core.voice_engine")

# Emoji stripping regex: ONLY allow ASCII printable + Devanagari (Hindi)
# This explicitly blocks all emoji Unicode blocks
EMOJI_PATTERN = re.compile(
    r'[\U0001F600-\U0001F64F'   # Emoticons
    r'\U0001F300-\U0001F5FF'    # Misc Symbols and Pictographs
    r'\U0001F680-\U0001F6FF'    # Transport and Map
    r'\U0001F1E0-\U0001F1FF'    # Flags
    r'\U00002702-\U000027B0'    # Dingbats
    r'\U000024C2-\U0001F251'    # Enclosed chars
    r'\U0001f926-\U0001f937'    # Supplemental
    r'\U00010000-\U0010ffff'    # Remaining supplementary
    r'\u2640-\u2642'
    r'\u2600-\u2B55'
    r'\u200d\ufe0f]+',
    flags=re.UNICODE
)

def strip_emojis(text: str) -> str:
    """Aggressively remove all emoji characters, keeping only readable text."""
    return EMOJI_PATTERN.sub('', text).strip()

# Initialize the pygame mixer for audio playback
try:
    pygame.mixer.init(frequency=24000)
except Exception as e:
    logger.warning(f"Failed to initialize pygame mixer: {e}")

def listen() -> str:
    """
    Captures audio locally from the default microphone and converts it to text.
    Uses Google STT which supports Hindi + English natively.
    """
    recognizer = sr.Recognizer()
    
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold = 300
    recognizer.pause_threshold = 0.6
    
    with sr.Microphone() as source:
        logger.info("Voice Engine: Listening to active microphone...")
        recognizer.adjust_for_ambient_noise(source, duration=0.2)
        
        try:
            logger.info("Voice Engine: Speak now (Hindi or English)...")
            audio = recognizer.listen(source, timeout=4, phrase_time_limit=10)
            logger.info("Voice Engine: Processing captured speech...")
            
            text = recognizer.recognize_google(audio, language="en-IN")
            logger.info(f"Voice Engine recognized: '{text}'")
            return text
            
        except sr.WaitTimeoutError:
            logger.warning("Voice Engine: Microphone timeout. No speech detected.")
            return ""
        except sr.UnknownValueError:
            logger.warning("Voice Engine: Speech unintelligible to the recognizer.")
            return ""
        except Exception as e:
            logger.error(f"Voice Engine Error: {e}")
            return ""

class StreamingTTS:
    """
    Queued TTS engine that processes chunks sequentially without dropping audio.
    The asyncio.Queue is created lazily the first time it is needed, ensuring
    it always belongs to the running event loop (not the import-time loop).
    """
    
    def __init__(self):
        self._queue: asyncio.Queue | None = None
        self._worker_running = False

    @property
    def queue(self) -> asyncio.Queue:
        """Lazily create the queue on first access inside the event loop."""
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue
        
    async def add_chunk(self, text: str):
        """Strip emojis and queue text for speaking."""
        clean_text = strip_emojis(text)
        if not clean_text or len(clean_text) < 2:
            return
        
        await self.queue.put(clean_text)
        
        # Start the worker if it's not already running
        if not self._worker_running:
            self._worker_running = True
            asyncio.create_task(self._worker())
            
    async def _worker(self):
        """Process TTS chunks one by one until the queue is drained."""
        try:
            while True:
                try:
                    # Wait up to 1 second for a new chunk before declaring done
                    chunk = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    break  # No more chunks coming, exit worker
                    
                logger.info(f"TTS Worker: Speaking -> '{chunk[:50]}'")
                
                temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
                try:
                    communicate = edge_tts.Communicate(chunk, "en-IN-NeerjaNeural", rate="+10%")
                    await communicate.save(temp_file)
                    
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy():
                        await asyncio.sleep(0.02)
                        
                    pygame.mixer.music.unload()
                except Exception as e:
                    logger.error(f"TTS Chunk Exception: {e}")
                finally:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception:
                        pass
        finally:
            self._worker_running = False
            # Reset queue so next session gets a fresh one
            self._queue = None

# Global singleton
tts_manager = StreamingTTS()

async def speak(text: str):
    """Legacy-compatible single-shot speaker."""
    await tts_manager.add_chunk(text)
