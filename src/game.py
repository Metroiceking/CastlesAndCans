# Game logic and UI for Castles & Cans
# Placeholder implementation for Raspberry Pi hardware integration

import os
import random
import datetime
import tkinter as tk
from enum import Enum, auto
import subprocess
import shutil

try:
    from PIL import Image, ImageTk  # Requires Pillow and ImageTk support
except Exception as exc:  # Pillow may be missing or compiled without tkinter
    Image = None
    ImageTk = None
    print(f"[Init] Pillow ImageTk unavailable: {exc}")

class Team(Enum):
    RED = 'Red'
    GREEN = 'Green'


class GameState(Enum):
    WAITING_START = auto()
    COIN_FLIP = auto()
    PLAYER_TURN = auto()
    AWAITING_TUNNEL = auto()
    AWAITING_LAUNCH = auto()
    BALL_LAUNCHED = auto()
    CHUG = auto()
    GAME_OVER = auto()


class HardwareInterface:
    """Placeholder methods for hardware actions."""

    def start_chug(self, team: Team):
        print(f"[HW] START_CHUG for {team.value}")

    def stop_chug(self, team: Team):
        print(f"[HW] STOP_CHUG for {team.value}")

    def hit_target(self, target: int):
        print(f"[HW] HIT_TARGET_{target}")

    def drop_gate(self):
        print("[HW] DROP_GATE")

    def dispense(self, team: Team):
        print(f"[HW] DISPENSE_{team.value}")

    def activate_tunnel(self, tunnel: int):
        print(f"[HW] ACTIVATE_TUNNEL_{tunnel}")

    def launch_plunger(self):
        """Fire the plunger to launch the ball."""
        print("[HW] LAUNCH_PLUNGER")

    def restore_targets(self, team: Team, hits: int):
        """Reset the physical targets to match the team's progress."""
        print(f"[HW] RESTORE_TARGETS for {team.value} at hit count {hits}")


class CameraInterface:
    """Handle capturing images from the Pi camera."""

    def __init__(self, capture_dir: str = "captures"):
        self.capture_dir = capture_dir
        os.makedirs(self.capture_dir, exist_ok=True)

    def capture_image(self, prefix: str) -> str:
        """Capture an image and return the file path."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.jpg"
        path = os.path.join(self.capture_dir, filename)
        # Placeholder for actual camera command. Replace with picamera2 or
        # libcamera-still on the Raspberry Pi.
        print(f"[HW] CAPTURE_IMAGE {path}")
        with open(path, "wb") as f:
            pass
        return path


class RCloneUploader:
    """Upload files using rclone and remove them locally."""

    def __init__(self, remote: str | None = None):
        self.remote = remote
        self.enabled = False
        if not remote:
            print("[RClone] RCLONE_REMOTE not set. Upload disabled")
            return
        if shutil.which("rclone") is None:
            print("[RClone] rclone command not found. Upload disabled")
            return
        self.enabled = True
        print(f"[RClone] Uploader configured for {self.remote}")

    def upload(self, filepath: str):
        if not self.enabled:
            print("[RClone] Upload skipped - uploader not configured")
            if os.path.exists(filepath):
                os.remove(filepath)
            return

        try:
            subprocess.check_call(["rclone", "copy", filepath, self.remote])
            print(f"[RClone] Uploaded {filepath}")
        except Exception as exc:
            print(f"[RClone] Failed to upload {filepath}: {exc}")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)


class CastlesAndCansGame:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.state = GameState.WAITING_START
        self.hw = HardwareInterface()
        self.current_team = None
        self.target_hits = {Team.RED: 0, Team.GREEN: 0}
        self.expected_target = {Team.RED: 1, Team.GREEN: 1}
        self.awaiting_tunnel = False
        self.prev_status = ""
        self.camera = CameraInterface()
        self.drive = RCloneUploader(os.environ.get("RCLONE_REMOTE"))
        self.chug_photo = None
        self.setup_ui()
        # Bind all key events so they register regardless of focus
        self.root.bind_all('<Key>', self.handle_key)
        self.ball_in_play = False

    def setup_ui(self):
        self.root.title("Castles & Cans")
        self.status_label = tk.Label(self.root, text="Press START", font=("Arial", 24))
        self.status_label.pack(pady=20)

        self.start_button = tk.Button(self.root, text="Start / Reset", command=self.start_game)
        self.start_button.pack(side=tk.LEFT, padx=10)

        self.force_next_button = tk.Button(self.root, text="Force Next Turn", command=self.next_turn)
        self.force_next_button.pack(side=tk.LEFT, padx=10)

        self.dispense_red = tk.Button(self.root, text="Dispense Red", command=lambda: self.dispense_beer(Team.RED))
        self.dispense_red.pack(side=tk.LEFT, padx=10)

        self.dispense_green = tk.Button(self.root, text="Dispense Green", command=lambda: self.dispense_beer(Team.GREEN))
        self.dispense_green.pack(side=tk.LEFT, padx=10)

        self.progress_frame = tk.Frame(self.root)
        self.progress_labels = []
        for _ in range(5):
            lbl = tk.Label(self.progress_frame, text="○", font=("Arial", 24))
            lbl.pack(side=tk.LEFT, padx=4)
            self.progress_labels.append(lbl)
        self.progress_frame.pack(pady=10)

        self.target_label = tk.Label(self.root, text="", font=("Arial", 18))
        self.target_label.pack(pady=5)

        self.ball_label = tk.Label(self.root, text="", font=("Arial", 18))
        self.ball_label.pack(pady=5)

        self.image_label = tk.Label(self.root)
        self.image_label.pack(pady=5)

        # Ensure key events go to the root window
        self.root.focus_set()

    def start_game(self):
        self.state = GameState.COIN_FLIP
        self.status_label.config(text="Flipping coin...")
        self.ball_label.config(text="")
        self.target_label.config(text="")
        self.image_label.config(image='')
        self.chug_photo = None
        self.ball_in_play = False
        self.target_hits = {Team.RED: 0, Team.GREEN: 0}
        self.expected_target = {Team.RED: 1, Team.GREEN: 1}
        self.hw.restore_targets(Team.RED, 0)
        self.hw.restore_targets(Team.GREEN, 0)
        self.root.after(1000, self.finish_coin_flip)

    def finish_coin_flip(self):
        self.current_team = random.choice([Team.RED, Team.GREEN])
        self.status_label.config(text=f"{self.current_team.value} starts - hit target {self.expected_target[self.current_team]}")
        self.hw.restore_targets(self.current_team, self.target_hits[self.current_team])
        self.state = GameState.PLAYER_TURN
        self.update_progress()
        self.ball_label.config(text="Throw ball at the castle")

    def hit_target(self, target: int):
        """Register a target hit. Always output the hardware event.

        Progress only advances when the game is in ``PLAYER_TURN`` state and
        the correct target for the current team is hit. Other hits merely show a
        message so key presses are visible when testing.
        """
        self.hw.hit_target(target)
        self.capture_image("hit")

        if self.state != GameState.PLAYER_TURN:
            # Show feedback even if the hit occurs at the wrong time
            self.status_label.config(text=f"Target {target} hit (not your turn)")
            return

        if target == self.expected_target[self.current_team]:
            self.target_hits[self.current_team] += 1
            self.expected_target[self.current_team] += 1
            self.update_progress()
            if self.target_hits[self.current_team] >= 5:
                self.win_game()
                return
            self.status_label.config(text=f"Target {target} hit! Await tunnel")
            self.state = GameState.AWAITING_TUNNEL
            self.awaiting_tunnel = True
        else:
            print("[HW] NEUTRAL_SOUND")
            self.status_label.config(text=f"Target {target} hit out of order - await tunnel")
            self.awaiting_tunnel = False
            self.state = GameState.AWAITING_TUNNEL

    def win_game(self):
        """Handle a victory for the current team."""
        self.state = GameState.GAME_OVER
        self.ball_in_play = False
        self.status_label.config(text=f"{self.current_team.value} WINS!")
        self.ball_label.config(text="")
        self.hw.drop_gate()

    def start_chug_phase(self):
        """Begin the chug phase once the ball launches."""
        self.state = GameState.CHUG
        self.hw.start_chug(self.current_team)
        self.status_label.config(text=f"{self.current_team.value} CHUG!")
        self.ball_label.config(text="Ball launched - chug!")
        # Capture a chug photo after a short delay but don't display it yet
        self.root.after(2000, lambda: setattr(self, 'chug_photo', self.capture_image('chug', show=False)))

    def end_chug_phase(self):
        self.hw.stop_chug(self.current_team)
        self.next_turn()

    def launch_ball(self):
        """Fire the plunger when the game is ready."""
        if self.state != GameState.AWAITING_LAUNCH:
            return
        self.hw.launch_plunger()
        self.ball_in_play = True
        if self.awaiting_tunnel:
            self.start_chug_phase()
        else:
            self.state = GameState.BALL_LAUNCHED
            self.ball_label.config(text="Ball launched - waiting for return")
            self.status_label.config(text="Ball launched")
        # Clear hit photo once the ball is launched
        self.image_label.config(image='')

    def tunnel_triggered(self):
        """Handle the ball entering the tunnel."""
        if self.state not in (
            GameState.AWAITING_TUNNEL,
            GameState.BALL_LAUNCHED,
            GameState.PLAYER_TURN,
        ):
            return

        self.hw.activate_tunnel(1)
        self.ball_in_play = False
        self.state = GameState.AWAITING_LAUNCH

        if self.awaiting_tunnel:
            self.status_label.config(text=f"{self.current_team.value} target cleared! Preparing launch")
        else:
            self.status_label.config(text="Ball entered tunnel")

        self.root.after(2000, self.ready_to_launch)

    def ready_to_launch(self):
        """Display a prompt that the plunger may be fired."""
        if self.state == GameState.AWAITING_LAUNCH:
            self.status_label.config(text="Ready to launch - press L")

    def dispense_beer(self, team: Team):
        self.prev_status = self.status_label.cget("text")
        self.status_label.config(text=f"Dispensing beer for {team.value}")
        self.hw.dispense(team)
        self.root.after(2000, lambda: self.status_label.config(text=self.prev_status))

    def ball_returned(self):
        if self.state == GameState.CHUG:
            self.hw.stop_chug(self.current_team)
            self.ball_label.config(text="Ball returned! Stop chugging")
            self.ball_in_play = False
            if self.chug_photo:
                self.image_label.config(image=self.chug_photo)
            if self.state != GameState.GAME_OVER:
                self.root.after(2000, self.next_turn)
        elif self.ball_in_play:
            self.ball_label.config(text="Ball returned")
            self.ball_in_play = False
            if self.state != GameState.GAME_OVER:
                self.root.after(1000, self.next_turn)

    def next_turn(self):
        if self.current_team is None:
            return
        self.current_team = Team.GREEN if self.current_team == Team.RED else Team.RED
        self.status_label.config(text=f"{self.current_team.value} turn - hit target {self.expected_target[self.current_team]}")
        self.hw.restore_targets(self.current_team, self.target_hits[self.current_team])
        self.update_progress()
        self.ball_in_play = False
        self.ball_label.config(text="Throw ball at the castle")
        self.awaiting_tunnel = False
        self.chug_photo = None
        self.image_label.config(image='')
        self.state = GameState.PLAYER_TURN

    def update_progress(self):
        hits = self.target_hits[self.current_team]
        for i, lbl in enumerate(self.progress_labels):
            if i < hits:
                color = 'red' if self.current_team == Team.RED else 'green'
                lbl.config(text='●', fg=color)
            else:
                lbl.config(text='○', fg='black')
        self.target_label.config(text=f"Next target: {self.expected_target[self.current_team]}")

    def capture_image(self, prefix: str, show: bool = True):
        """Capture an image, optionally display it, then upload to Drive."""
        path = self.camera.capture_image(prefix)
        photo = None
        if Image and ImageTk:
            try:
                img = Image.open(path)
                img.thumbnail((320, 240))
                photo = ImageTk.PhotoImage(img)
                if show:
                    self.image_label.config(image=photo)
                    self.image_label.image = photo
            except Exception as exc:
                print(f"Failed to load image {path}: {exc}")
        else:
            print("[Init] Pillow not available - skipping image preview")
        self.drive.upload(path)
        return photo

    def handle_key(self, event):
        key = event.keysym.lower()
        if key == 's':
            self.start_game()
        elif key == 'n':
            self.next_turn()
        elif key == 'r':
            self.dispense_beer(Team.RED)
        elif key == 'g':
            self.dispense_beer(Team.GREEN)
        elif key in ['1', '2', '3', '4', '5']:
            self.hit_target(int(key))
        elif key == 't':
            self.tunnel_triggered()
        elif key == 'b':
            self.ball_returned()
        elif key == 'l':
            self.launch_ball()


if __name__ == "__main__":
    root = tk.Tk()
    game = CastlesAndCansGame(root)
    root.mainloop()
