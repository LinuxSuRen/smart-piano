#!/usr/bin/env python3
"""
Smart Piano Web Server
Streams MIDI events from the electronic piano to the browser via WebSocket.
Supports recording and playback of MIDI performances.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import mido
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

RECORDINGS_DIR = Path("recordings")

app = FastAPI(title="Smart Piano")

connected_clients: set[WebSocket] = set()

midi_connected: bool = False
recording_active: bool = False
recorded_events: list[tuple[float, mido.Message]] = []
recording_start_time: float = 0.0
playback_active: bool = False
latest_filename: str | None = None
app_event_loop: asyncio.AbstractEventLoop | None = None
midi_input_port: mido.ports.BaseInput | None = None
midi_output_port: mido.ports.BaseOutput | None = None


def midi_to_note_name(midi_note: int) -> str:
    if not (0 <= midi_note <= 127):
        return "??"
    name = NOTE_NAMES[midi_note % 12]
    octave = (midi_note // 12) - 1
    return f"{name}{octave}"


async def broadcast_event(event: dict) -> None:
    dead: set[WebSocket] = set()
    payload = json.dumps(event)
    for ws in connected_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


def midi_message_to_event(message: mido.Message, source: str = "live") -> dict | None:
    if message.type == "note_on" and message.velocity > 0:
        return {
            "type": "note_on",
            "note": message.note,
            "name": midi_to_note_name(message.note),
            "velocity": message.velocity,
            "channel": message.channel,
            "source": source,
        }
    elif message.type == "note_off" or (
        message.type == "note_on" and message.velocity == 0
    ):
        return {
            "type": "note_off",
            "note": message.note,
            "name": midi_to_note_name(message.note),
            "channel": message.channel,
            "source": source,
        }
    return None


def on_midi_message(message: mido.Message) -> None:
    event = midi_message_to_event(message, source="live")
    if event is None:
        return

    if recording_active:
        elapsed = time.monotonic() - recording_start_time
        recorded_events.append((elapsed, message))

    if app_event_loop is not None:
        asyncio.run_coroutine_threadsafe(broadcast_event(event), app_event_loop)


@app.post("/record/start")
async def start_recording() -> JSONResponse:
    global recording_active, recorded_events, recording_start_time
    if not midi_connected:
        return JSONResponse({"ok": False, "error": "No MIDI device connected — recording unavailable"})
    if recording_active:
        return JSONResponse({"ok": False, "error": "Already recording"})
    recorded_events = []
    recording_start_time = time.monotonic()
    recording_active = True
    await broadcast_event({"type": "recording_status", "active": True})
    return JSONResponse({"ok": True})


@app.post("/record/stop")
async def stop_recording() -> JSONResponse:
    global recording_active, latest_filename
    if not recording_active:
        return JSONResponse({"ok": False, "error": "Not recording"})
    recording_active = False
    await broadcast_event({"type": "recording_status", "active": False})

    if not recorded_events:
        return JSONResponse({"ok": True, "filename": None, "duration": 0, "events": 0})

    RECORDINGS_DIR.mkdir(exist_ok=True)
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))

    prev_time = 0.0
    for elapsed, msg in recorded_events:
        delta_seconds = elapsed - prev_time
        ticks = int(delta_seconds * (480 * 2))  # 120 BPM = 2 beats/sec, 480 ticks/beat
        prev_time = elapsed
        out_msg = msg.copy(time=max(0, ticks))
        track.append(out_msg)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    latest_filename = f"recording_{timestamp}.mid"
    mid.save(str(RECORDINGS_DIR / latest_filename))

    duration = recorded_events[-1][0] if recorded_events else 0
    return JSONResponse(
        {"ok": True, "filename": latest_filename, "duration": round(duration, 1), "events": len(recorded_events)}
    )


@app.post("/play/latest")
async def play_latest() -> JSONResponse:
    global playback_active
    if not latest_filename:
        return JSONResponse({"ok": False, "error": "No recording available"})
    filepath = RECORDINGS_DIR / latest_filename
    if not filepath.exists():
        return JSONResponse({"ok": False, "error": "Recording file not found"})
    asyncio.create_task(play_midi_file(filepath))
    return JSONResponse({"ok": True, "filename": latest_filename})


@app.get("/recordings")
async def list_recordings() -> JSONResponse:
    RECORDINGS_DIR.mkdir(exist_ok=True)
    files = sorted(RECORDINGS_DIR.glob("*.mid"), key=os.path.getmtime, reverse=True)
    return JSONResponse(
        [{"filename": f.name, "size": f.stat().st_size} for f in files]
    )


@app.post("/play/{filename}")
async def play_file(filename: str) -> JSONResponse:
    filepath = RECORDINGS_DIR / filename
    if not filepath.exists():
        return JSONResponse({"ok": False, "error": "File not found"}, status_code=404)
    asyncio.create_task(play_midi_file(filepath))
    return JSONResponse({"ok": True, "filename": filename})


@app.post("/record/cancel")
async def cancel_recording() -> JSONResponse:
    global recording_active, recorded_events
    recording_active = False
    recorded_events = []
    await broadcast_event({"type": "recording_status", "active": False})
    return JSONResponse({"ok": True})


async def play_midi_file(filepath: Path) -> None:
    global playback_active
    playback_active = True
    await broadcast_event({"type": "playback_start", "filename": filepath.name})

    mid = mido.MidiFile(str(filepath))
    tempo = 500000

    for msg in mid.play():
        if msg.type == "set_tempo":
            tempo = msg.tempo
            continue
        if not playback_active:
            break

        if midi_output_port is not None and not msg.is_meta:
            midi_output_port.send(msg)

        event = midi_message_to_event(msg, source="playback")
        if event:
            await broadcast_event(event)
        await asyncio.sleep(msg.time / 1000)

    playback_active = False
    await broadcast_event({"type": "playback_end"})


@app.post("/play/stop")
async def stop_playback() -> JSONResponse:
    global playback_active
    playback_active = False
    return JSONResponse({"ok": True})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    connected_clients.add(ws)

    await ws.send_text(json.dumps({"type": "recording_status", "active": recording_active}))
    await ws.send_text(json.dumps({"type": "midi_status", "connected": midi_connected}))

    try:
        while True:
            data = await ws.receive_text()
            try:
                cmd = json.loads(data)
                await handle_ws_command(cmd)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)


async def handle_ws_command(cmd: dict) -> None:
    action = cmd.get("action", "")
    if action == "start_recording":
        await start_recording()
    elif action == "stop_recording":
        await stop_recording()
    elif action == "play_latest":
        await play_latest()
    elif action == "play_file":
        filename = cmd.get("filename", "")
        if filename:
            filepath = RECORDINGS_DIR / filename
            if filepath.exists():
                global playback_active
                playback_active = False
                await asyncio.sleep(0.05)
                asyncio.create_task(play_midi_file(filepath))
    elif action == "stop_playback":
        await stop_playback()


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    with open("static/index.html") as f:
        return HTMLResponse(f.read())


async def serve() -> None:
    global app_event_loop
    app_event_loop = asyncio.get_running_loop()
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="error")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    global midi_connected, midi_input_port, midi_output_port

    port_name = select_midi_port()
    if port_name is None:
        print("⚠ No MIDI input device found — running in playback-only mode.")
        print("  Connect a MIDI device and restart the server to enable live input & recording.")
        midi_connected = False
    else:
        print(f"MIDI input: {port_name}")
        midi_input_port = mido.open_input(port_name, callback=on_midi_message)
        midi_connected = True

    out_names = mido.get_output_names()
    if out_names:
        midi_output_port = mido.open_output(out_names[0])
        print(f"MIDI output: {out_names[0]}")
    else:
        print("No MIDI output ports found — playback will be visual only")

    print("Starting server at http://localhost:8000")
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
    finally:
        if midi_input_port is not None:
            midi_input_port.close()
        if midi_output_port is not None:
            midi_output_port.close()
        print("Stopped.")


def select_midi_port() -> str | None:
    names = mido.get_input_names()
    if not names:
        print("No MIDI input ports detected.", file=sys.stderr)
        return None
    if len(names) == 1:
        print(f"Auto-selected MIDI port: {names[0]}")
        return names[0]

    print("Available MIDI input ports:\n")
    for i, name in enumerate(names):
        print(f"  [{i}]  {name}")
    print()
    while True:
        try:
            choice = input("Select port number: ").strip()
            idx = int(choice)
            if 0 <= idx < len(names):
                return names[idx]
            print(f"Please enter 0–{len(names) - 1}.")
        except ValueError:
            print("Please enter a number.")
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)


if __name__ == "__main__":
    main()
