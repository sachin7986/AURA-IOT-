# AURA — AI-Powered Voice Assistant with IoT Control

> **A**dvanced **U**nified **R**esponsive **A**ssistant — A smart, bilingual AI desktop assistant with real-time voice control, system automation, and IoT home device management.

---

## What is AURA?

AURA is a full-stack AI assistant built as an IoT mini-project. It understands natural language commands in **English and Hinglari (Hinglish)**, executes system-level tasks on your PC, and controls real-world hardware — lights, fans, AC, and TV — through a NodeMCU ESP8266 over WiFi.

You can talk to it, type to it, or use the web UI. It responds with voice, text, and live feedback on an LCD display connected to the NodeMCU.

---

## Features

- **Voice control** — Speak in English or Hinglish; AURA understands and responds
- **AI conversation** — Powered by Llama 3.3 70B via Groq for fast, natural responses
- **System automation** — Open/close apps, type text, take screenshots, search files, play YouTube
- **IoT device control** — Turn light, fan, AC, and TV on/off via relay module over WiFi
- **LCD dashboard** — Real-time device status shown on a 16×2 I2C LCD on the NodeMCU
- **Memory system** — Remembers your name and preferences across sessions
- **Chat history** — Full session storage and search via MongoDB
- **Streaming TTS** — Speaks responses word by word using Microsoft Edge Neural TTS

---

## Tech Stack

### Backend (Python)
| Component | Technology |
|---|---|
| Web framework | FastAPI |
| LLM provider | Groq API (Llama 3.3 70B) |
| Speech-to-Text | Google STT via `SpeechRecognition` |
| Text-to-Speech | Microsoft Edge TTS (`edge-tts`) |
| Audio playback | Pygame |
| Database | MongoDB (Motor async driver) |
| System automation | PyAutoGUI, `os`, `subprocess` |
| Environment | Python 3.10+ |

### Frontend
| Component | Technology |
|---|---|
| UI framework | React + Vite |
| Styling | Custom CSS |
| Communication | WebSocket + REST API |

### Hardware (IoT)
| Component | Details |
|---|---|
| Microcontroller | NodeMCU ESP8266 |
| Display | 16×2 LCD with I2C backpack (address 0x27) |
| Switching | 4-channel relay module (active-LOW) |
| Devices | Bulb, fan, AC, TV (via relay contacts) |
| Protocol | HTTP REST over WiFi |
| Firmware | Arduino C++ (Arduino IDE) |

---

## Project Architecture

```
User (Voice / Text)
        │
        ▼
  FastAPI Backend
        │
   ┌────┴────┐
   │  Router  │ ◄── command_parser.py (regex, no LLM cost)
   └────┬────┘
        │
   ┌────┴──────────────┐
   │                   │
Planner (LLM)    LLM Engine (LLM)
task JSON list    conversation / Q&A
   │
   ▼
Executor
   │
   ├── open_app / close_app  ──► os.system / taskkill
   ├── write_text            ──► PyAutoGUI keyboard simulation
   ├── play_youtube          ──► webbrowser
   ├── screenshot            ──► system_actions
   ├── get_weather           ──► weather API
   └── light / fan / ac / tv ──► HTTP GET ──► NodeMCU ESP8266
                                                    │
                                              Relay Module
                                                    │
                                           Physical Appliance
```

---

## How the IoT Part Works

1. NodeMCU connects to WiFi on boot and starts an HTTP server on port 80
2. Each device has its own endpoint: `/ON`, `/OFF`, `/FAN_ON`, `/FAN_OFF`, `/AC_ON`, `/AC_OFF`, `/TV_ON`, `/TV_OFF`
3. When AURA receives a voice command like *"turn on the light"*, the Python backend sends `GET http://<NodeMCU-IP>/ON`
4. NodeMCU receives the request, sets the relay GPIO pin LOW (active-LOW relay), closing the relay contact
5. The appliance circuit completes and the device turns on
6. NodeMCU updates the I2C LCD with the new device state and sends HTTP 200 back to Python
7. AURA speaks the confirmation back to the user

---

## Hardware Setup

```
NodeMCU Pin Layout:
┌─────────────────────────────┐
│  D4 (GPIO2)  ──► Relay IN1  │  Light
│  D5 (GPIO14) ──► Relay IN2  │  Fan
│  D6 (GPIO12) ──► Relay IN3  │  AC
│  D7 (GPIO13) ──► Relay IN4  │  TV
│  D1 (GPIO5)  ──► LCD SCL    │  I2C Clock
│  D2 (GPIO4)  ──► LCD SDA    │  I2C Data
│  3.3V / GND  ──► LCD VCC/GND│
│  5V / GND    ──► Relay VCC/GND
└─────────────────────────────┘
```

> **Note:** Relay module uses active-LOW logic. `digitalWrite(pin, LOW)` = device ON. `digitalWrite(pin, HIGH)` = device OFF. All relays are set HIGH at boot for safety.

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB running locally or via Atlas
- Groq API key (free at [console.groq.com](https://console.groq.com))
- NodeMCU ESP8266 with relay module (for IoT features)

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/aura-assistant.git
cd aura-assistant
```

### 2. Set up environment variables

Create a `.env` file in the backend root:

```env
GROQ_API_KEY=your_groq_api_key_here
MONGO_URI=mongodb://localhost:27017/
NODEMCU_IP=192.168.x.x
```

### 3. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
```

### 5. Flash the NodeMCU

- Open `nodemcu/aura_nodemcu.ino` in Arduino IDE
- Install libraries: `ESP8266WiFi`, `ESP8266WebServer`, `LiquidCrystal_I2C`
- Update `ssid` and `password` in the sketch
- Flash to your NodeMCU board
- Note the IP address shown on the LCD and update `NODEMCU_IP` in `.env`

### 6. Run the project

```bash
# Terminal 1 — Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Voice Commands (Examples)

| What you say | What happens |
|---|---|
| `"Turn on the light"` | Relay 1 closes → bulb turns on |
| `"Band karo fan"` | Fan relay opens → fan stops |
| `"Open notepad and write an email about internship"` | Opens Notepad, generates email via LLM, types it |
| `"Play Shape of You on YouTube"` | Opens YouTube search |
| `"What's the weather in Ludhiana"` | Fetches and speaks weather |
| `"Take a screenshot"` | Captures screen and saves |
| `"Set volume to 60"` | Sets system volume |
| `"Mera naam kya hai"` | Reads from memory and responds |

---

## Memory System

AURA has two memory layers:

- **Short-term** — Last 10 messages of the current session, injected into every LLM prompt as context
- **Long-term** — Persistent user facts stored in `memory_store.json` (e.g. your name, preferences). Survives restarts.

To teach AURA something permanently:
```
"Remember that my name is Arjun"
"Remember that I prefer dark mode"
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Send a text message |
| `WS` | `/ws/chat` | WebSocket for streaming responses |
| `GET` | `/api/history` | List all chat sessions |
| `GET` | `/api/history/{id}` | Get a specific session |
| `DELETE` | `/api/history/{id}` | Delete a session |
| `GET` | `/health` | Health check |

### NodeMCU Endpoints (direct)

| Endpoint | Action |
|---|---|
| `/ON` / `/OFF` | Light on/off |
| `/FAN_ON` / `/FAN_OFF` | Fan on/off |
| `/AC_ON` / `/AC_OFF` | AC on/off |
| `/TV_ON` / `/TV_OFF` | TV on/off |
| `/STATUS` | Returns JSON state of all devices |

---

## Project Structure

```
aura-assistant/
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── core/
│   │   ├── router.py         # Command routing logic
│   │   ├── command_parser.py # Regex-based fast parser
│   │   ├── planner.py        # LLM task decomposition
│   │   ├── executor.py       # Task execution engine
│   │   ├── llm_engine.py     # Groq LLM integration
│   │   ├── fast_engine.py    # System commands (apps, web)
│   │   ├── system_actions.py # OS-level actions
│   │   ├── voice_engine.py   # STT + TTS
│   │   ├── memory.py         # Memory system
│   │   ├── memory_store.json # Persistent preferences
│   │   └── chat_history.py   # MongoDB session manager
│   └── routes/
│       ├── api.py            # REST routes
│       ├── ws.py             # WebSocket routes
│       └── history.py        # Chat history routes
├── frontend/
│   ├── index.html
│   └── src/
│       └── main.jsx
└── nodemcu/
    └── aura_nodemcu.ino      # ESP8266 firmware
```

---

## Known Limitations

- NodeMCU IP is hardcoded — assign a static IP in your router for reliability
- Voice input requires an active internet connection for Google STT
- System automation features (open apps, type text) are Windows-only
- PyAutoGUI typing requires the target window to be in focus

---

## Future Improvements

- [ ] MQTT support for more reliable IoT communication
- [ ] Temperature and humidity sensor integration (DHT11/DHT22)
- [ ] Mobile app for remote control
- [ ] Wake word detection ("Hey AURA")
- [ ] Cross-platform support (Linux/macOS)
- [ ] OTA (Over-the-Air) firmware updates for NodeMCU

---

## Built With

- [Groq](https://groq.com) — Ultra-fast LLM inference
- [Meta Llama 3.3 70B](https://ai.meta.com) — Open source language model
- [FastAPI](https://fastapi.tiangolo.com) — Python web framework
- [Edge TTS](https://github.com/rany2/edge-tts) — Microsoft Neural TTS
- [ESP8266 Arduino Core](https://github.com/esp8266/Arduino) — NodeMCU firmware

---

## License

MIT License — feel free to use, modify, and build on this project.

---

## Author

Built as an IoT mini-project.  
If you found this useful, drop a ⭐ on the repo!
