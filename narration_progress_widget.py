#!/usr/bin/env python3
"""Small always-on-top widget showing VibeVoice narration generation progress
on the TrueNAS sandbox. Polls over SSH every 20s."""
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk

TOTAL_SCENES = 13
SSH_KEY = "/home/allan/.ssh/truenas_video_ed25519"
HOST = "claude@truenas.home"
PORT = "2222"
POLL_SECONDS = 20

SCENE_IDS = [
    "title", "what_is", "itar", "ear", "differences", "license_requirements",
    "daily", "red_flags", "penalties", "responsibilities", "quiz", "summary", "closing",
]


def check_progress():
    try:
        result = subprocess.run(
            ["ssh", "-i", SSH_KEY, "-p", PORT, "-o", "ConnectTimeout=8", HOST,
             "ls ~/out/*.wav 2>/dev/null | wc -l; "
             "grep -c ALL_NARRATION_DONE ~/narration.log 2>/dev/null || true"],
            capture_output=True, text=True, timeout=15,
        )
        lines = result.stdout.strip().splitlines()
        count = int(lines[0]) if lines and lines[0].isdigit() else 0
        done = len(lines) > 1 and lines[1].strip() not in ("", "0")
        return count, done
    except Exception as e:
        return None, False


class ProgressWidget:
    def __init__(self, root):
        self.root = root
        root.title("VibeVoice Narration Progress")
        root.attributes("-topmost", True)
        root.geometry("380x140+40+40")
        root.resizable(False, False)

        self.title_label = tk.Label(root, text="ITAR/EAR Training Video - Narration",
                                     font=("Sans", 11, "bold"))
        self.title_label.pack(pady=(12, 4))

        self.bar = ttk.Progressbar(root, orient="horizontal", length=320,
                                    mode="determinate", maximum=TOTAL_SCENES)
        self.bar.pack(pady=8)

        self.status_label = tk.Label(root, text="Checking...", font=("Sans", 10))
        self.status_label.pack()

        self.scene_label = tk.Label(root, text="", font=("Sans", 9), fg="#555")
        self.scene_label.pack(pady=(2, 0))

        self.updated_label = tk.Label(root, text="", font=("Sans", 8), fg="#888")
        self.updated_label.pack(side="bottom", pady=(0, 6))

        self.poll_loop()

    def poll_loop(self):
        threading.Thread(target=self._poll_once, daemon=True).start()
        self.root.after(POLL_SECONDS * 1000, self.poll_loop)

    def _poll_once(self):
        count, done = check_progress()
        self.root.after(0, self._update_ui, count, done)

    def _update_ui(self, count, done):
        now = time.strftime("%H:%M:%S")
        if count is None:
            self.status_label.config(text="Connection failed - retrying...", fg="#c00")
            self.updated_label.config(text=f"Last attempt: {now}")
            return

        self.bar["value"] = count
        if done or count >= TOTAL_SCENES:
            self.status_label.config(text=f"Done! {count}/{TOTAL_SCENES} scenes complete", fg="#080")
            self.scene_label.config(text="Ready to assemble the final video.")
        else:
            self.status_label.config(text=f"{count}/{TOTAL_SCENES} scenes complete", fg="#000")
            current = SCENE_IDS[count] if count < len(SCENE_IDS) else "?"
            self.scene_label.config(text=f"Currently rendering: {current}")
        self.updated_label.config(text=f"Last checked: {now}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ProgressWidget(root)
    root.mainloop()
