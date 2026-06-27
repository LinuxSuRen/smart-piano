# Smart Piano

Real-time MIDI piano visualization and recording. Connect your electronic piano via USB, play, and watch the notes come alive in your browser.

## Features

- **Live MIDI Monitor** — see every note you play in the terminal
- **Web Visualization** — canvas-based piano keyboard with particle effects, falling note symbols, and jianpu (简谱) display
- **Record & Playback** — record sessions to `.mid` files and play them back through your piano
- **Dark UI** — atmospheric dark theme with color-coded notes and smooth animations

## Setup

```bash
pip install -r requirements.txt
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
