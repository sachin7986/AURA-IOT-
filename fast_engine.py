import pyautogui
import time
import logging

logger = logging.getLogger("aura.core.fast_engine")

# Safety configuration for pyautogui
pyautogui.FAILSAFE = True

def _human_type(text: str, delay: float = 0.05):
    """Types out text with a small delay between keystrokes to mimic human typing."""
    for char in text:
        pyautogui.write(char)
        time.sleep(delay)

import os
import subprocess
import webbrowser

def open_app_system(app_name: str) -> str:
    """
    Opens an application securely using native Windows OS commands instead of GUI simulation.
    """
    app_name = app_name.lower().strip()
    logger.info(f"Fast Engine: Executing System Command to open -> {app_name}")
    
    # Robust mapping for common alias names
    app_map = {
        "notepad": "notepad",
        "file explorer": "explorer",
        "explorer": "explorer",
        "chrome": "chrome",
        "google chrome": "chrome",
        "calculator": "calc",
        "calc": "calc",
        "cmd": "cmd",
        "command prompt": "cmd"
    }
    
    executable = app_map.get(app_name, app_name)
    
    # Complete execution validation block
    if "whatsapp" in app_name:
        logger.info("Executing specialized WhatsApp environment check...")
        
        # Strategy A: Check legacy standalone installer path
        local_path = os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe")
        if os.path.exists(local_path):
            os.system(f"start \"\" \"{local_path}\"")
            return "Successfully launched WhatsApp Desktop."
            
        # Strategy B: Check modern Microsoft Store App context
        try:
            check_uwp = subprocess.run(
                ["powershell", "-Command", "Get-AppxPackage -Name *WhatsApp*"], 
                capture_output=True, text=True, timeout=2
            )
            has_uwp = "WhatsApp" in check_uwp.stdout
        except:
            has_uwp = False
            
        if has_uwp:
            os.system("start whatsapp:")
            return "Successfully triggered WhatsApp Desktop."
        else:
            # Fallback Strategy: Web
            logger.warning("WhatsApp Desktop binary missing. Defaulting to WhatsApp Web fallback.")
            webbrowser.open("https://web.whatsapp.com")
            return "I couldn't find the WhatsApp Desktop app installed, so I opened WhatsApp Web in your browser instead!"
            
    try:
        # Standard generic execution
        exit_code = os.system(f"start {executable}")
        
        # Verify edge cases where 'start' fails cleanly without throwing a hard native exception
        if exit_code == 0:
            return f"Successfully executed system command to launch: {app_name}"
        else:
            return f"Error executing launch command. The executable '{app_name}' could not be located in your system PATH."
            
    except Exception as e:
        logger.error(f"Failed to OS execute {app_name}: {e}")
        return f"System Execution Error: Application not found or could not be triggered."


def close_app_system(app_name: str) -> str:
    """
    Closes/kills a running application using taskkill.
    Returns real success/failure status.
    """
    app_name = app_name.lower().strip()
    logger.info(f"Fast Engine: Closing app -> {app_name}")
    
    # Map friendly names to actual process names
    process_map = {
        "notepad": "notepad.exe",
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "file explorer": "explorer.exe",
        "explorer": "explorer.exe",
        "calculator": "CalculatorApp.exe",
        "calc": "CalculatorApp.exe",
        "cmd": "cmd.exe",
        "command prompt": "cmd.exe",
        "whatsapp": "WhatsApp.exe",
        "spotify": "Spotify.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
        "firefox": "firefox.exe",
        "vlc": "vlc.exe",
        "vscode": "Code.exe",
        "vs code": "Code.exe",
    }
    
    process_name = process_map.get(app_name, f"{app_name}.exe")
    
    try:
        # First check if the process is actually running
        check = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=3
        )
        
        if "No tasks" in check.stdout or process_name.lower() not in check.stdout.lower():
            logger.warning(f"Process {process_name} is not running.")
            return f"{app_name} is not currently running."
        
        # Kill it
        result = subprocess.run(
            ["taskkill", "/IM", process_name, "/F"],
            capture_output=True, text=True, timeout=5
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully killed {process_name}")
            return f"Successfully closed {app_name}."
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            logger.error(f"taskkill failed for {process_name}: {error_msg}")
            return f"Could not close {app_name}: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return f"Timeout while trying to close {app_name}."
    except Exception as e:
        logger.error(f"close_app_system error: {e}")
        return f"Error closing {app_name}: {e}"

def open_website(url: str) -> str:
    """
    Opens a website by using the standard Python webbrowser module.
    """
    try:
        if not url.startswith("http"):
            url = "https://" + url
            
        logger.info(f"Fast Engine: Using native webbrowser to open -> {url}")
        webbrowser.open(url)
        return f"Successfully executed native command to open website: {url}"
    
    except Exception as e:
        logger.error(f"Failed to open website {url}: {e}")
        return f"Error opening website: {e}"

import urllib.parse

def play_on_youtube(query: str) -> str:
    """
    Opens YouTube and performs a search for the requested video/song.
    """
    try:
        encoded_query = urllib.parse.quote(query.strip())
        # sp=EgIQAQ%253D%253D filters for videos only to increase "Direct hit" chances
        url = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAQ%253D%253D"
        
        logger.info(f"Fast Engine: Playing on YouTube -> '{query}'")
        webbrowser.open(url)
        return f"Successfully opened YouTube and searching for: {query}"
    
    except Exception as e:
        logger.error(f"Failed to play on YouTube {query}: {e}")
        return f"Error playing on YouTube: {e}"

from core.system_actions import execute_system_action

def control_system(action: str) -> str:
    """
    Routes system control commands to the real system_actions dispatcher.
    """
    logger.info(f"Fast Engine: System control -> {action}")
    return execute_system_action(action)

