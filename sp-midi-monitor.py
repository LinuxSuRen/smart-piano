#!/usr/bin/env python3
"""
Smart Piano MIDI Monitor
Reads MIDI input from an electronic piano and prints note events in real time.
"""

import sys
import signal

import mido

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note_name(midi_note: int) -> str:
    if not (0 <= midi_note <= 127):
        return "??"
    name = NOTE_NAMES[midi_note % 12]
    octave = (midi_note // 12) - 1
    return f"{name}{octave}"


def on_midi_message(message: mido.Message) -> None:
    if message.type == "note_on" and message.velocity > 0:
        note_str = midi_to_note_name(message.note)
        print(
            f"\x1b[32m◆ Note ON \x1b[0m"
            f"  {note_str:<5}"
            f"  velocity={message.velocity:<3d}"
            f"  ch={message.channel + 1}"
        )

    elif message.type == "note_off" or (
        message.type == "note_on" and message.velocity == 0
    ):
        note_str = midi_to_note_name(message.note)
        print(
            f"\x1b[31m◇ Note OFF\x1b[0m"
            f"  {note_str:<5}"
            f"  velocity={message.velocity:<3d}"
            f"  ch={message.channel + 1}"
        )

    elif message.type in ("control_change", "program_change", "pitchwheel"):
        pass


def select_input_port() -> str:
    names = mido.get_input_names()

    if not names:
        print("No MIDI input ports detected.", file=sys.stderr)
        print("Make sure your piano is connected and powered on.", file=sys.stderr)
        sys.exit(1)

    print("Available MIDI input ports:\n")
    for i, name in enumerate(names):
        print(f"  [{i}]  {name}")

    if len(names) == 1:
        print(f"\nOnly one port found — auto-selecting: {names[0]}")
        return names[0]

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


def main() -> None:
    print("=" * 52)
    print("  Smart Piano MIDI Monitor")
    print("  Press Ctrl+C to stop")
    print("=" * 52)
    print()

    port_name = select_input_port()

    print(f"\nListening on: {port_name}")
    print("─" * 52)
    print(f"{'Event':<12} {'Note':<8} {'Velocity':<10} {'Channel'}")
    print("─" * 52)

    with mido.open_input(port_name, callback=on_midi_message):
        signal.pause()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped.")
        sys.exit(0)
