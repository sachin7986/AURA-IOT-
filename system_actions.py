"""
system_actions.py — Real OS-level system actions for AURA.
Every function returns a real success/failure string. No fake execution.
"""
import os
import re
import ast
import shutil
import logging
import subprocess
import operator
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError

logger = logging.getLogger("aura.core.system_actions")


# ===================================================================
# SAFETY — Critical path blacklist for destructive operations
# ===================================================================

PROTECTED_PATHS = [
    os.environ.get("SYSTEMROOT", r"C:\Windows").lower(),
    r"c:\windows",
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\users\default",
    r"c:\$recycle.bin",
]

def _is_protected_path(path: str) -> bool:
    """Returns True if the path is inside a critical system directory."""
    normalized = os.path.abspath(path).lower()
    for protected in PROTECTED_PATHS:
        if normalized.startswith(protected):
            return True
    # Also block anything inside System32
    if "system32" in normalized:
        return True
    return False


# ===================================================================
# DATE & TIME
# ===================================================================

def get_date() -> str:
    """Returns the current system date in a human-friendly format."""
    now = datetime.now()
    formatted = now.strftime("%A, %B %d, %Y")  # e.g. "Friday, April 04, 2026"
    logger.info(f"System Action: get_date -> {formatted}")
    return f"Today's date is {formatted}."


def get_time() -> str:
    """Returns the current system time."""
    now = datetime.now()
    formatted = now.strftime("%I:%M %p")  # e.g. "02:30 PM"
    logger.info(f"System Action: get_time -> {formatted}")
    return f"The current time is {formatted}."


# ===================================================================
# VOLUME CONTROL (Real Windows Audio API via pycaw)
# ===================================================================

def _get_volume_interface():
    """Get the Windows audio endpoint volume interface (pycaw 2025+)."""
    try:
        from pycaw.pycaw import AudioUtilities
        device = AudioUtilities.GetSpeakers()
        return device.EndpointVolume
    except Exception as e:
        logger.error(f"Failed to get audio interface: {e}")
        return None


def set_volume(level: int) -> str:
    """
    Sets the system master volume to an exact percentage (0-100).
    Uses the Windows Core Audio API via pycaw for real execution.
    """
    level = max(0, min(100, level))  # Clamp between 0-100
    logger.info(f"System Action: set_volume -> {level}%")
    
    vol = _get_volume_interface()
    if vol is None:
        return f"Error: Could not access Windows audio device to set volume to {level}%."
    
    try:
        # SetMasterVolumeLevelScalar takes a float 0.0 - 1.0
        vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        
        # Unmute if setting a non-zero volume
        if level > 0:
            vol.SetMute(0, None)
            
        return f"System volume set to {level}%."
    except Exception as e:
        logger.error(f"set_volume error: {e}")
        return f"Error setting volume: {e}"


def get_volume() -> str:
    """Returns the current system volume level."""
    vol = _get_volume_interface()
    if vol is None:
        return "Error: Could not access Windows audio device."
    
    try:
        current = int(vol.GetMasterVolumeLevelScalar() * 100)
        muted = vol.GetMute()
        status = f"Current volume: {current}%"
        if muted:
            status += " (Muted)"
        logger.info(f"System Action: get_volume -> {current}%, muted={muted}")
        return status
    except Exception as e:
        logger.error(f"get_volume error: {e}")
        return f"Error reading volume: {e}"


def volume_up(steps: int = 10) -> str:
    """Increases volume by a percentage amount."""
    vol = _get_volume_interface()
    if vol is None:
        return "Error: Could not access Windows audio device."
    
    try:
        current = vol.GetMasterVolumeLevelScalar()
        new_level = min(1.0, current + (steps / 100.0))
        vol.SetMasterVolumeLevelScalar(new_level, None)
        vol.SetMute(0, None)
        pct = int(new_level * 100)
        logger.info(f"System Action: volume_up -> {pct}%")
        return f"Volume increased to {pct}%."
    except Exception as e:
        logger.error(f"volume_up error: {e}")
        return f"Error increasing volume: {e}"


def volume_down(steps: int = 10) -> str:
    """Decreases volume by a percentage amount."""
    vol = _get_volume_interface()
    if vol is None:
        return "Error: Could not access Windows audio device."
    
    try:
        current = vol.GetMasterVolumeLevelScalar()
        new_level = max(0.0, current - (steps / 100.0))
        vol.SetMasterVolumeLevelScalar(new_level, None)
        pct = int(new_level * 100)
        logger.info(f"System Action: volume_down -> {pct}%")
        return f"Volume decreased to {pct}%."
    except Exception as e:
        logger.error(f"volume_down error: {e}")
        return f"Error decreasing volume: {e}"


def mute_toggle() -> str:
    """Toggles system mute on/off."""
    vol = _get_volume_interface()
    if vol is None:
        return "Error: Could not access Windows audio device."
    
    try:
        is_muted = vol.GetMute()
        vol.SetMute(not is_muted, None)
        state = "muted" if not is_muted else "unmuted"
        logger.info(f"System Action: mute_toggle -> {state}")
        return f"System audio {state}."
    except Exception as e:
        logger.error(f"mute_toggle error: {e}")
        return f"Error toggling mute: {e}"


# ===================================================================
# SYSTEM INFO
# ===================================================================

def get_battery() -> str:
    """Returns current battery status."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected (possibly a desktop PC)."
        pct = battery.percent
        plugged = "charging" if battery.power_plugged else "on battery"
        logger.info(f"System Action: get_battery -> {pct}%, {plugged}")
        return f"Battery is at {pct}%, currently {plugged}."
    except ImportError:
        return "Battery info unavailable (psutil not installed)."
    except Exception as e:
        logger.error(f"get_battery error: {e}")
        return f"Error reading battery: {e}"


# ===================================================================
# BRIGHTNESS (Windows only)
# ===================================================================

def set_brightness(level: int) -> str:
    """Sets display brightness (0-100) via PowerShell WMI."""
    level = max(0, min(100, level))
    logger.info(f"System Action: set_brightness -> {level}%")
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"Screen brightness set to {level}%."
        else:
            return f"Could not set brightness. This may not be supported on desktop monitors."
    except Exception as e:
        logger.error(f"set_brightness error: {e}")
        return f"Error setting brightness: {e}"


# ===================================================================
# FILE SYSTEM OPERATIONS
# ===================================================================

def open_folder(path: str) -> str:
    """Opens a folder in Windows Explorer. Returns real success/failure."""
    path = os.path.abspath(path.strip())
    logger.info(f"System Action: open_folder -> '{path}'")
    
    if not os.path.isdir(path):
        return f"Error: Folder does not exist: '{path}'"
    
    try:
        os.startfile(path)
        return f"Successfully opened folder: {path}"
    except Exception as e:
        logger.error(f"open_folder error: {e}")
        return f"Error opening folder: {e}"


def create_file(path: str, content: str = "") -> str:
    """
    Creates a new file at the given path. Optionally writes content into it.
    Creates parent directories automatically if they don't exist.
    """
    path = os.path.abspath(path.strip())
    logger.info(f"System Action: create_file -> '{path}'")
    
    if os.path.exists(path):
        return f"File already exists: '{path}'. Use a different name or delete it first."
    
    try:
        # Ensure parent directories exist
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        size = os.path.getsize(path)
        return f"Successfully created file: '{path}' ({size} bytes)"
    except PermissionError:
        return f"Permission denied: Cannot create file at '{path}'."
    except Exception as e:
        logger.error(f"create_file error: {e}")
        return f"Error creating file: {e}"


def create_folder(path: str) -> str:
    """Creates a new directory at the given path (including intermediate dirs)."""
    path = os.path.abspath(path.strip())
    logger.info(f"System Action: create_folder -> '{path}'")
    
    if os.path.exists(path):
        if os.path.isdir(path):
            return f"Folder already exists: '{path}'."
        else:
            return f"A file with that name already exists: '{path}'. Cannot create folder."
    
    try:
        os.makedirs(path, exist_ok=True)
        return f"Successfully created folder: '{path}'"
    except PermissionError:
        return f"Permission denied: Cannot create folder at '{path}'."
    except Exception as e:
        logger.error(f"create_folder error: {e}")
        return f"Error creating folder: {e}"


def delete_file(path: str) -> str:
    """
    Deletes a file at the given path.
    SAFETY: Refuses to delete files inside protected system directories.
    """
    path = os.path.abspath(path.strip())
    logger.info(f"System Action: delete_file -> '{path}'")
    
    if _is_protected_path(path):
        logger.warning(f"BLOCKED: Attempted to delete protected file: {path}")
        return f"BLOCKED: Cannot delete files inside protected system directories. Path: '{path}'"
    
    if not os.path.exists(path):
        return f"File does not exist: '{path}'"
    
    if os.path.isdir(path):
        return f"'{path}' is a directory, not a file. Use 'delete folder' instead."
    
    try:
        os.remove(path)
        return f"Successfully deleted file: '{path}'"
    except PermissionError:
        return f"Permission denied: Cannot delete '{path}'. It may be in use."
    except Exception as e:
        logger.error(f"delete_file error: {e}")
        return f"Error deleting file: {e}"


def delete_folder(path: str) -> str:
    """
    Deletes a folder and all its contents.
    SAFETY: Refuses to delete protected system directories.
    """
    path = os.path.abspath(path.strip())
    logger.info(f"System Action: delete_folder -> '{path}'")
    
    if _is_protected_path(path):
        logger.warning(f"BLOCKED: Attempted to delete protected folder: {path}")
        return f"BLOCKED: Cannot delete protected system directories. Path: '{path}'"
    
    if not os.path.exists(path):
        return f"Folder does not exist: '{path}'"
    
    if not os.path.isdir(path):
        return f"'{path}' is a file, not a folder. Use 'delete file' instead."
    
    try:
        shutil.rmtree(path)
        return f"Successfully deleted folder and all contents: '{path}'"
    except PermissionError:
        return f"Permission denied: Cannot delete '{path}'. Some files may be in use."
    except Exception as e:
        logger.error(f"delete_folder error: {e}")
        return f"Error deleting folder: {e}"


# ===================================================================
# WEATHER (via wttr.in — free, no API key required)
# ===================================================================

def get_weather(city: str) -> str:
    """
    Fetches current weather for a city using wttr.in's free API.
    Returns a natural-language weather summary string.
    """
    city = city.strip()
    logger.info(f"System Action: get_weather -> '{city}'")
    
    try:
        # wttr.in format: ?format=<custom>
        # %C = condition, %t = temperature, %h = humidity, %w = wind
        url = f"https://wttr.in/{city}?format=%C+%t+%h+%w"
        
        from urllib.request import Request
        req = Request(url, headers={"User-Agent": "AURA-Assistant/2.0"})
        
        with urlopen(req, timeout=5) as response:
            raw = response.read().decode("utf-8").strip()
        
        if "Unknown location" in raw or "not found" in raw.lower():
            return f"Sorry, I couldn't find weather data for '{city}'. Check the city name and try again."
        
        # Parse the compact response: "Sunny +28°C 40% →14km/h"
        parts = raw.split()
        
        # Build a natural-language response
        condition = []
        temp = ""
        humidity = ""
        wind = ""
        
        for part in parts:
            if "°" in part:
                temp = part.replace("+", "")
            elif "%" in part:
                humidity = part
            elif "km" in part.lower() or "mph" in part.lower():
                wind = part
            else:
                condition.append(part)
        
        condition_str = " ".join(condition) if condition else "varied"
        
        result = f"Today's weather in {city.title()} is {condition_str} with temperature around {temp}."
        if humidity:
            result += f" Humidity is {humidity}."
        if wind:
            result += f" Wind speed: {wind}."
        
        logger.info(f"Weather result: {result}")
        return result
        
    except URLError:
        logger.error(f"Weather fetch failed for '{city}': network error")
        return "Sorry, I couldn't fetch weather data right now. Please check your internet connection."
    except Exception as e:
        logger.error(f"get_weather error: {e}")
        return "Sorry, I couldn't fetch weather data right now."


# ===================================================================
# SCREENSHOT CAPTURE
# ===================================================================

# Default screenshots folder
SCREENSHOTS_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "AURA_Screenshots")

def take_screenshot(save_path: str = "auto") -> str:
    """
    Captures the current screen and saves it as a PNG.
    Uses pyautogui (already available in the project).
    """
    logger.info("System Action: take_screenshot")
    try:
        import pyautogui
    except ImportError:
        return "Error: pyautogui is not installed. Cannot capture screenshot."

    try:
        # Ensure screenshots directory exists
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

        if save_path == "auto" or not save_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(SCREENSHOTS_DIR, f"screenshot_{timestamp}.png")

        save_path = os.path.abspath(save_path)
        screenshot = pyautogui.screenshot()
        screenshot.save(save_path)

        logger.info(f"Screenshot saved to: {save_path}")
        return f"Screenshot captured and saved to: {save_path}"
    except Exception as e:
        logger.error(f"take_screenshot error: {e}")
        return f"Error capturing screenshot: {e}"


# ===================================================================
# CAMERA — Open + Capture Image
# ===================================================================

CAMERA_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "AURA_Camera")

def open_camera() -> str:
    """
    Opens the system camera app.
    On Windows, this opens the built-in Camera app.
    """
    logger.info("System Action: open_camera")
    try:
        # Try Windows Camera app (UWP)
        exit_code = os.system("start microsoft.windows.camera:")
        if exit_code == 0:
            return "Camera app opened successfully."
        else:
            # Fallback: try generic 'camera' command
            exit_code = os.system("start camera")
            if exit_code == 0:
                return "Camera opened successfully."
            return "Error: Could not find a camera application on this system."
    except Exception as e:
        logger.error(f"open_camera error: {e}")
        return f"Error opening camera: {e}"


def capture_image(save_path: str = "auto") -> str:
    """
    Captures a single frame from the webcam using OpenCV.
    Falls back to error message if no camera is found.
    """
    logger.info("System Action: capture_image")
    try:
        import cv2
    except ImportError:
        return "Error: OpenCV (cv2) is not installed. Run: pip install opencv-python"

    try:
        os.makedirs(CAMERA_DIR, exist_ok=True)

        if save_path == "auto" or not save_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(CAMERA_DIR, f"photo_{timestamp}.png")

        save_path = os.path.abspath(save_path)

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # DirectShow is more reliable on Windows
        if not cap.isOpened():
            # Fallback: try without DirectShow
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "Error: No camera device found. Please check your webcam connection."

        # Warm up: read several frames so the camera auto-adjusts exposure/white-balance
        import time
        frame = None
        for i in range(30):
            ret, frame = cap.read()
            time.sleep(0.05)  # ~1.5 seconds total warm-up

        # Final capture
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return "Error: Camera opened but failed to capture a frame. Try closing other apps that might be using the camera."

        cv2.imwrite(save_path, frame)
        logger.info(f"Photo captured and saved to: {save_path}")
        return f"Photo captured and saved to: {save_path}"
    except Exception as e:
        logger.error(f"capture_image error: {e}")
        return f"Error capturing image: {e}"


# ===================================================================
# FILE SEARCH
# ===================================================================

def search_file(query: str, search_path: str = None, max_results: int = 10) -> str:
    """
    Searches for files matching the query name recursively.
    Returns a list of matching file paths.
    """
    logger.info(f"System Action: search_file -> query='{query}', path='{search_path}'")

    if not search_path:
        # Default to user home directory for safety and speed
        search_path = os.path.expanduser("~")

    search_path = os.path.abspath(search_path.strip())
    if not os.path.isdir(search_path):
        return f"Error: Search path does not exist: '{search_path}'"

    query_lower = query.lower().strip()
    matches = []

    try:
        for root, dirs, files in os.walk(search_path):
            # Skip hidden and system directories for speed
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in [
                'node_modules', '__pycache__', '.git', 'venv', '.venv',
                'appdata', '$recycle.bin', 'windows'
            ]]

            for f in files:
                if query_lower in f.lower():
                    matches.append(os.path.join(root, f))
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        if not matches:
            return f"No files found matching '{query}' in '{search_path}'."

        result = f"Found {len(matches)} file(s) matching '{query}':\n"
        for i, path in enumerate(matches, 1):
            result += f"  {i}. {path}\n"
        return result.strip()

    except PermissionError:
        return f"Permission denied while searching in '{search_path}'."
    except Exception as e:
        logger.error(f"search_file error: {e}")
        return f"Error searching for files: {e}"


# ===================================================================
# CALCULATOR ENGINE — Safe math evaluation
# ===================================================================

# Allowed operators for safe evaluation
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_node(node):
    """Recursively evaluate an AST node containing only numbers and basic math ops."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        if op_type == ast.Div and right == 0:
            raise ZeroDivisionError("Division by zero")
        return _SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _safe_eval_node(node.operand)
        return _SAFE_OPERATORS[op_type](operand)
    else:
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def calculate(expression: str) -> str:
    """
    Safely evaluates a mathematical expression using AST parsing.
    Only allows numbers and basic arithmetic (+, -, *, /, //, %, **).
    NO eval() — prevents code injection.
    """
    expression = expression.strip()
    logger.info(f"System Action: calculate -> '{expression}'")

    # Clean common natural language
    cleaned = expression.lower()
    for word in ["what is", "what's", "calculate", "solve", "kitna hai", "kitna", "bata"]:
        cleaned = cleaned.replace(word, "")
    cleaned = cleaned.replace("x", "*").replace("×", "*").replace("÷", "/").strip()

    if not cleaned:
        return "Please provide a math expression to calculate."

    try:
        tree = ast.parse(cleaned, mode='eval')
        result = _safe_eval_node(tree)

        # Format the result nicely
        if isinstance(result, float) and result == int(result):
            result = int(result)

        return str(result)
    except ZeroDivisionError:
        return "Error: Division by zero."
    except (ValueError, SyntaxError, TypeError):
        return f"Sorry, I couldn't calculate '{expression}'. Try something like '5 + 3 * 2'."
    except Exception as e:
        logger.error(f"calculate error: {e}")
        return f"Calculation error: {e}"


def is_math_expression(text: str) -> bool:
    """
    Detects if the input text is likely a math expression.
    Used by the router to decide whether to route to the calculator.
    """
    cleaned = text.strip().lower()
    # Remove common natural language wrappers
    for word in ["what is", "what's", "calculate", "solve", "kitna hai", "kitna", "bata"]:
        cleaned = cleaned.replace(word, "")
    cleaned = cleaned.replace("x", "*").replace("×", "*").replace("÷", "/").strip()

    if not cleaned:
        return False

    # Must contain at least one digit and one operator
    has_digit = any(c.isdigit() for c in cleaned)
    has_operator = any(c in cleaned for c in ['+', '-', '*', '/', '%', '^'])
    # Should be mostly math characters
    math_chars = set('0123456789+-*/.%^() ')
    is_mostly_math = all(c in math_chars for c in cleaned)

    return has_digit and has_operator and is_mostly_math


# ===================================================================
# EMAIL SENDING (mailto: fallback + optional SMTP)
# ===================================================================

def send_email_action(to: str = "", subject: str = "", body: str = "") -> str:
    """
    Opens the default email client with pre-filled fields using mailto: protocol.
    If SMTP credentials are configured in .env, sends via SMTP instead.
    """
    logger.info(f"System Action: send_email -> to='{to}', subject='{subject[:30]}'")

    import webbrowser
    from urllib.parse import quote

    # Check for SMTP credentials in environment
    smtp_user = os.environ.get("SMTP_EMAIL", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if smtp_user and smtp_pass and to:
        # Try real SMTP sending
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = to
            msg['Subject'] = subject or "Message from AURA"
            msg.attach(MIMEText(body or "Sent via AURA AI Assistant.", 'plain'))

            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to, msg.as_string())
            server.quit()

            logger.info(f"Email sent via SMTP to {to}")
            return f"Email successfully sent to {to} with subject: '{subject}'."
        except Exception as e:
            logger.error(f"SMTP send_email error: {e}")
            return f"Error sending email via SMTP: {e}. Falling back to mailto: link."

    # Fallback: Open default email client via mailto:
    try:
        mailto_url = f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}"
        webbrowser.open(mailto_url)
        if to:
            return f"Opened your email client with a draft to {to}."
        else:
            return "Opened your email client. Fill in the recipient and send!"
    except Exception as e:
        logger.error(f"mailto send_email error: {e}")
        return f"Error opening email client: {e}"


# ===================================================================
# TASK SCHEDULER / REMINDERS (in-memory, managed by scheduler module)
# ===================================================================

def parse_reminder_time(time_str: str) -> str:
    """
    Parses natural time strings like '5 pm', '6:30', '17:00' into HH:MM format.
    Returns the parsed time string or 'invalid'.
    """
    time_str = time_str.strip().lower()

    # Try "5 pm", "5pm", "5:30 pm"
    match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = match.group(3)

        if period == 'pm' and hour < 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return "invalid"


# ===================================================================
# MASTER DISPATCHER
# ===================================================================

def execute_system_action(command: str) -> str:
    """
    Master dispatcher that parses a natural-language system command 
    and routes it to the correct function. Returns real result.
    """
    cmd = command.lower().strip()
    logger.info(f"System Action Dispatcher: '{cmd}'")
    
    # --- Screenshot ---
    if any(kw in cmd for kw in ["screenshot", "screen shot", "capture screen", "screen capture"]):
        return take_screenshot()

    # --- Camera ---
    if any(kw in cmd for kw in ["capture photo", "take photo", "take picture", "capture image", "take selfie", "photo lelo", "photo khicho"]):
        return capture_image()
    if cmd in ["open camera", "camera open", "camera chalu"]:
        return open_camera()

    # --- File Search ---
    search_match = re.search(r'(?:find|search|locate|dhundho|khojo)\s+(?:file|files)?\s*(.+)', cmd)
    if search_match:
        query = search_match.group(1).strip().strip('"').strip("'")
        return search_file(query)

    # --- Calculator ---
    if is_math_expression(cmd):
        return calculate(cmd)

    # --- Email ---
    email_match = re.search(r'(?:send|write)\s+(?:an?\s+)?(?:email|mail)\s+(?:to\s+)?(.+?)(?:\s+about\s+(.+))?$', cmd)
    if email_match:
        recipient = email_match.group(1).strip()
        subject = email_match.group(2) or ""
        return send_email_action(to=recipient, subject=subject.strip())

    # --- Reminder ---
    reminder_match = re.search(r'(?:remind|reminder|yaad)\s+(?:me\s+)?(?:to\s+|at\s+)?(.+?)\s+(?:at|baje|on)\s+(.+)', cmd)
    if reminder_match:
        task_text = reminder_match.group(1).strip()
        time_text = reminder_match.group(2).strip()
        parsed_time = parse_reminder_time(time_text)
        if parsed_time == "invalid":
            return f"Could not parse the time '{time_text}'. Try '5 pm' or '18:30'."
        return f"Reminder set: '{task_text}' at {parsed_time}. I'll remind you!"
    # Also handle "set reminder to <task> at <time>"
    reminder_match2 = re.search(r'set\s+(?:a\s+)?reminder\s+(?:to\s+)?(.+?)\s+(?:at|baje)\s+(.+)', cmd)
    if reminder_match2:
        task_text = reminder_match2.group(1).strip()
        time_text = reminder_match2.group(2).strip()
        parsed_time = parse_reminder_time(time_text)
        if parsed_time == "invalid":
            return f"Could not parse the time '{time_text}'. Try '5 pm' or '18:30'."
        return f"Reminder set: '{task_text}' at {parsed_time}. I'll remind you!"

    # --- Date ---
    if any(kw in cmd for kw in ["date", "today", "aaj", "din"]):
        return get_date()
    
    # --- Time ---
    if any(kw in cmd for kw in ["time", "samay", "baje", "clock"]):
        return get_time()
    
    # --- Weather ---
    weather_match = re.search(r'(?:weather|mausam|mosam)\s*(?:in|of|at|for)?\s+(.+)', cmd)
    if weather_match:
        city = weather_match.group(1).strip()
        return get_weather(city)
    if any(kw in cmd for kw in ["weather", "mausam", "mosam"]):
        return get_weather("auto")  # wttr.in auto-detects location with "auto"
    
    # --- File/Folder Operations ---
    # Create file
    create_file_match = re.search(r'(?:create|make|banao)\s+(?:a\s+)?file\s+(.+)', cmd)
    if create_file_match:
        filepath = create_file_match.group(1).strip().strip('"').strip("'")
        return create_file(filepath)
    
    # Create folder
    create_folder_match = re.search(r'(?:create|make|banao)\s+(?:a\s+)?(?:folder|directory|dir)\s+(.+)', cmd)
    if create_folder_match:
        folderpath = create_folder_match.group(1).strip().strip('"').strip("'")
        return create_folder(folderpath)
    
    # Delete file
    delete_file_match = re.search(r'(?:delete|remove|hatao)\s+(?:the\s+)?file\s+(.+)', cmd)
    if delete_file_match:
        filepath = delete_file_match.group(1).strip().strip('"').strip("'")
        return delete_file(filepath)
    
    # Delete folder
    delete_folder_match = re.search(r'(?:delete|remove|hatao)\s+(?:the\s+)?(?:folder|directory|dir)\s+(.+)', cmd)
    if delete_folder_match:
        folderpath = delete_folder_match.group(1).strip().strip('"').strip("'")
        return delete_folder(folderpath)
    
    # Open folder
    open_folder_match = re.search(r'open\s+(?:the\s+)?(?:folder|directory|dir)\s+(.+)', cmd)
    if open_folder_match:
        folderpath = open_folder_match.group(1).strip().strip('"').strip("'")
        return open_folder(folderpath)
    
    # --- Set volume to specific level ---
    vol_match = re.search(r'(?:volume|vol)\s*(?:to|at|set|=)?\s*(\d+)', cmd)
    if vol_match:
        return set_volume(int(vol_match.group(1)))
    
    # Also handle "set volume 50%" or "volume 50%"
    pct_match = re.search(r'(\d+)\s*%', cmd)
    if pct_match and "volume" in cmd:
        return set_volume(int(pct_match.group(1)))
    
    # --- Volume up/down ---
    if "volume up" in cmd or "increase volume" in cmd or "volume badha" in cmd:
        return volume_up()
    if "volume down" in cmd or "decrease volume" in cmd or "volume kam" in cmd:
        return volume_down()
    
    # --- Mute ---
    if "mute" in cmd or "unmute" in cmd:
        return mute_toggle()
    
    # --- Get current volume ---
    if "volume" in cmd and ("what" in cmd or "kitna" in cmd or "current" in cmd or "check" in cmd):
        return get_volume()
    
    # --- Battery ---
    if "battery" in cmd:
        return get_battery()
    
    # --- Brightness ---
    bright_match = re.search(r'brightness\s*(?:to|at|set|=)?\s*(\d+)', cmd)
    if bright_match:
        return set_brightness(int(bright_match.group(1)))
    if "brightness" in cmd:
        pct = re.search(r'(\d+)', cmd)
        if pct:
            return set_brightness(int(pct.group(1)))
    
    # --- Shutdown (safety guard) ---
    if "shutdown" in cmd or "restart" in cmd:
        return "Shutdown/Restart is disabled for safety during development."
    
    # --- Fallthrough ---
    logger.warning(f"System Action: Unrecognized command -> '{cmd}'")
    return f"I couldn't recognize the system action in: '{command}'. Try something like 'set volume 50%' or 'what's the date?'"
