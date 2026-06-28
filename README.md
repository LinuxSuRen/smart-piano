# Smart Piano

Real-time MIDI piano visualization and recording. Connect your electronic piano via USB, play, and watch the notes come alive in your browser.

## Features

- **Staff Notation (五线谱)** — grand staff (treble + bass clef) shows notes in real time as they're played
- **Live MIDI Monitor** — see every note you play in the terminal
- **Web Visualization** — canvas-based piano keyboard with particle effects and falling note bars
- **Record & Playback** — record sessions to `.mid` files and play them back through your piano
- **Dark UI** — atmospheric dark theme with color-coded notes and smooth animations

## Setup

### System Dependencies

```bash
# Debian/Ubuntu
sudo apt install -y pkg-config libasound2-dev libjack-dev

# macOS
brew install pkg-config
```

### Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
# Web app with visualization (recommended)
python3 server.py
# Open http://localhost:8000

# Terminal monitor only
python3 sp-midi-monitor.py
```

## Controls

| Action | Button | Keyboard |
|--------|--------|----------|
| Record | ⏺ | `R` |
| Play latest | ▶ | `Space` |
| Stop | ⏹ | `Esc` |
| Browse recordings | ☰ | — |

Recordings are saved to `recordings/` as `.mid` files.

## Requirements

- Python 3.10+
- USB MIDI piano or keyboard
- macOS / Linux / Windows
