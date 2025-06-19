# Game logic and UI for Castles & Cans
# Placeholder implementation for Raspberry Pi hardware integration

import os
import random
import datetime
import tkinter as tk
from enum import Enum, auto
from typing import Optional
import subprocess
import shutil
import sys
import threading
import time
import json

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO_AVAILABLE = True
except Exception as exc:
    GPIO_AVAILABLE = False
    print(f"[GPIO] Hardware GPIO unavailable: {exc}")

try:
    import spidev
    SPI_AVAILABLE = True
except Exception as exc:
    spidev = None
    SPI_AVAILABLE = False
    print(f"[SPI] spidev unavailable: {exc}")

try:
    from PIL import Image, ImageTk  # Requires Pillow and ImageTk support
except Exception as exc:  # Pillow may be missing or compiled without tkinter
    Image = None
    ImageTk = None
    print(f"[Init] Pillow ImageTk unavailable: {exc}")

# Basic colors and fonts for a castle-style theme
BG_COLOR = "#352f2b"  # dark stone background
FG_COLOR = "#f0e6c8"  # parchment text
BUTTON_BG = "#5b4636"
TITLE_FONT = ("Times New Roman", 30, "bold")
LABEL_FONT = ("Times New Roman", 18, "bold")
BUTTON_FONT = ("Times New Roman", 16, "bold")
PROGRESS_FONT = ("Times New Roman", 24, "bold")

NUM_TARGETS = 7

# ---------------- GPIO PIN ASSIGNMENTS ----------------
# BCM numbering is used throughout
RELAY_FAN = 17
RELAY_RED_DISPENSE = 5
RELAY_GREEN_DISPENSE = 6
RELAY_EXPANSION_1 = 13
RELAY_EXPANSION_2 = 19
RELAY_EXPANSION_3 = 26

NEOPIXEL_PIN = 18

BUTTON_START = 23
BUTTON_FORCE_TURN = 24
BUTTON_RED_DISPENSE = 20
BUTTON_GREEN_DISPENSE = 21

IR_BALL_RETURN = 14
IR_TUNNEL_ENTRY = 15
IR_TARGET_1 = 0

MCP3008_CLK = 11
MCP3008_MISO = 9
MCP3008_MOSI = 10
MCP3008_CS = 8

SERVO_1 = 12  # Red team beer door
SERVO_2 = 16  # Green team beer door
SERVO_3 = 4
SERVO_4 = 3
SERVO_5 = 2
SERVO_6 = 27
SERVO_7 = 22
SERVO_8 = 7

# Pressure sensors via MCP3008 channels
PRESSURE_CHANNELS = [0, 1, 2, 3]
PRESSURE_SENSITIVITY = 200  # ADC threshold for detecting a hit

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


class SoundEffect(Enum):
    """Logical names for sound effects used throughout the game."""
    TARGET_HIT = auto()
    NEUTRAL_HIT = auto()
    CHUG_START = auto()
    CHUG_STOP = auto()
    GATE_BREACH = auto()
    VICTORY = auto()
    DISPENSE = auto()


class LedColor(Enum):
    """Placeholder LED colours."""
    RED = 'red'
    GREEN = 'green'
    OFF = 'off'


class HardwareInterface:
    """Basic GPIO control for the Castles & Cans hardware."""

    SERVO_STATE_FILE = "servo_state.json"
    START_ANGLE = 90

    def __init__(self, pressure_sensitivity: int = PRESSURE_SENSITIVITY):
        self.available = GPIO_AVAILABLE
        self.spi_available = SPI_AVAILABLE
        self.pressure_sensitivity = pressure_sensitivity
        self.servo_pins = [
            SERVO_1,
            SERVO_2,
            SERVO_3,
            SERVO_4,
            SERVO_5,
            SERVO_6,
            SERVO_7,
            SERVO_8,
        ]
        if self.available:
            outputs = [
                RELAY_FAN,
                RELAY_RED_DISPENSE,
                RELAY_GREEN_DISPENSE,
                RELAY_EXPANSION_1,
                RELAY_EXPANSION_2,
                RELAY_EXPANSION_3,
            ]
            for pin in outputs:
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

            for pin in [
                BUTTON_START,
                BUTTON_FORCE_TURN,
                BUTTON_RED_DISPENSE,
                BUTTON_GREEN_DISPENSE,
            ]:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            for pin in [IR_BALL_RETURN, IR_TUNNEL_ENTRY, IR_TARGET_1]:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            for pin in [
                SERVO_1,
                SERVO_2,
                SERVO_3,
                SERVO_4,
                SERVO_5,
                SERVO_6,
                SERVO_7,
                SERVO_8,
            ]:
                GPIO.setup(pin, GPIO.OUT)
        else:
            print("[GPIO] Running in mock mode")

        # SPI setup for MCP3008
        if self.spi_available:
            try:
                self.spi = spidev.SpiDev()
                self.spi.open(0, 0)
                self.spi.max_speed_hz = 1350000
            except Exception as exc:
                print(f"[SPI] Failed to open SPI: {exc}")
                self.spi_available = False
        else:
            print("[SPI] Using mock ADC readings")

        self._load_servo_state()
        self.reset_servos()

    def _load_servo_state(self):
        """Load last known servo angles from disk."""
        self.servo_state = {pin: self.START_ANGLE for pin in self.servo_pins}
        if os.path.exists(self.SERVO_STATE_FILE):
            try:
                with open(self.SERVO_STATE_FILE, "r") as fh:
                    data = json.load(fh)
                for pin, angle in data.items():
                    self.servo_state[int(pin)] = angle
            except Exception as exc:
                print(f"[Servo] Failed to load state: {exc}")

    def _save_servo_state(self):
        try:
            with open(self.SERVO_STATE_FILE, "w") as fh:
                json.dump(self.servo_state, fh)
        except Exception as exc:
            print(f"[Servo] Failed to save state: {exc}")

    def set_servo_angle(self, pin: int, angle: float):
        """Move servo to ``angle`` and record the position."""

        def worker():
            duty = self._angle_to_duty(angle)
            if self.available:
                pwm = GPIO.PWM(pin, 50)
                pwm.start(duty)
                time.sleep(0.5)
                pwm.stop()
            print(f"[GPIO] Servo {pin} -> {angle}°")

        threading.Thread(target=worker, daemon=True).start()
        self.servo_state[pin] = angle
        self._save_servo_state()

    def reset_servos(self):
        """Return all servos to the starting angle if needed."""
        for pin in self.servo_pins:
            if self.servo_state.get(pin, self.START_ANGLE) != self.START_ANGLE:
                self.set_servo_angle(pin, self.START_ANGLE)

    @staticmethod
    def _angle_to_duty(angle: float) -> float:
        """Convert a servo angle in degrees to a PWM duty cycle."""
        return 2.5 + (angle / 18.0)

    def rotate_servo(self, pin: int, angle: float, hold: float = 0, return_angle: float = 90):
        """Rotate a servo asynchronously and return it to ``return_angle``."""

        def worker():
            duty_start = self._angle_to_duty(angle)
            duty_return = self._angle_to_duty(return_angle)
            if self.available:
                pwm = GPIO.PWM(pin, 50)
                pwm.start(duty_start)
                time.sleep(0.5)
                if hold:
                    time.sleep(hold)
                pwm.ChangeDutyCycle(duty_return)
                time.sleep(0.5)
                pwm.stop()
            print(f"[GPIO] Servo {pin} rotate {angle}° for {hold}s then {return_angle}°")

        threading.Thread(target=worker, daemon=True).start()
        self.servo_state[pin] = return_angle
        self._save_servo_state()

    def _pulse(self, pin: int, duration: float = 0.5):
        """Pulse a GPIO output without blocking the main thread."""

        def worker():
            if self.available:
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(duration)
                GPIO.output(pin, GPIO.LOW)
            print(f"[GPIO] Pulse {pin} for {duration}s")

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- MCP3008 Pressure Sensor Helpers ----------------
    def read_adc(self, channel: int) -> int:
        """Read a value from the MCP3008 ADC."""
        if not 0 <= channel <= 7:
            raise ValueError("ADC channel must be 0-7")
        if self.spi_available:
            try:
                r = self.spi.xfer2([1, (8 + channel) << 4, 0])
                return ((r[1] & 3) << 8) | r[2]
            except Exception as exc:
                print(f"[SPI] Read failed: {exc}")
                return 0
        else:
            # No SPI available; return zero to avoid false hits
            return 0

    def check_pressure_hit(self, channel: int) -> bool:
        """Return True if the pressure sensor crosses the configured threshold."""
        value = self.read_adc(channel)
        if value > self.pressure_sensitivity:
            print(f"[Pressure] Channel {channel} hit value {value}")
            return True
        return False

    def play_sound(self, effect: SoundEffect):
        """Play a sound effect."""
        print(f"[Sound] {effect.name}")

    def set_target_led(self, target: int, color: LedColor):
        """Set an LED colour for a specific target."""
        print(f"[LED] Target {target} -> {color.value}")

    def set_theme_lighting(self, team: Optional[Team]):
        """Change theme lighting to match the active team or turn off."""
        value = team.value if team else 'off'
        print(f"[LED] Theme lighting -> {value}")

    def raise_pong_platform(self):
        """Raise the pong platform on victory."""
        self._pulse(RELAY_EXPANSION_2, 1)
        print("[HW] RAISE_PONG_PLATFORM")

    def blow_fan(self, duration: float = 5.0):
        """Activate the fan relay for the specified duration."""
        self._pulse(RELAY_FAN, duration)

    def start_chug(self, team: Team):
        print(f"[HW] START_CHUG for {team.value}")

    def stop_chug(self, team: Team):
        print(f"[HW] STOP_CHUG for {team.value}")

    def hit_target(self, target: int):
        print(f"[HW] HIT_TARGET_{target}")

    def drop_gate(self):
        print("[HW] DROP_GATE")

    def dispense(self, team: Team):
        pin = RELAY_RED_DISPENSE if team == Team.RED else RELAY_GREEN_DISPENSE
        self._pulse(pin, 1)
        if team == Team.RED:
            servo_pin = SERVO_1
            angle = 0  # 100° counterclockwise from centre
        else:
            servo_pin = SERVO_2
            angle = 180  # 100° clockwise from centre (clamped)
        self.rotate_servo(servo_pin, angle, hold=3)

    def activate_tunnel(self, tunnel: int):
        print(f"[HW] ACTIVATE_TUNNEL_{tunnel}")

    def launch_plunger(self):
        """Fire the plunger to launch the ball."""
        self._pulse(RELAY_EXPANSION_1, 0.2)
        print("[HW] LAUNCH_PLUNGER")

    def restore_targets(self, team: Team, hits: int):
        """Reset physical targets to the given hit count."""
        print(f"[HW] RESTORE_TARGETS for {team.value} at hit count {hits}")


class CameraInterface:
    """Handle capturing images from the Pi camera."""

    def __init__(self, capture_dir: str = "captures"):
        self.capture_dir = capture_dir
        os.makedirs(self.capture_dir, exist_ok=True)
        # Remove any leftover captures from a previous run
        for f in os.listdir(self.capture_dir):
            if f.lower().endswith(".jpg"):
                try:
                    os.remove(os.path.join(self.capture_dir, f))
                except OSError as exc:
                    print(f"[Camera] Failed to remove old capture {f}: {exc}")

        # Determine which camera command is available on the system.
        self.command = None
        if shutil.which("libcamera-still"):
            # ``libcamera-still`` is the default on newer Pi OS releases
            self.command = [
                "libcamera-still",
                "-n",
                "--immediate",
                "--width",
                "1280",
                "--height",
                "720",
                "-o",
            ]
        elif shutil.which("raspistill"):
            # ``raspistill`` for legacy camera stack
            self.command = [
                "raspistill",
                "-n",
                "-t",
                "1",
                "-w",
                "1280",
                "-h",
                "720",
                "-o",
            ]
        else:
            print("[Camera] No camera command found. Using placeholder images")

    def _placeholder_image(self, path: str):
        """Create a blank placeholder image when the camera is unavailable."""
        if Image:
            img = Image.new("RGB", (1280, 720), color="black")
            img.save(path)
        else:
            with open(path, "wb"):
                pass

    def capture_image(self, prefix: str) -> str:
        """Capture an image and return the file path."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.jpg"
        path = os.path.join(self.capture_dir, filename)

        if self.command:
            try:
                subprocess.check_call(
                    self.command + [path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                print(f"[Camera] Failed to capture image: {exc}")
                self._placeholder_image(path)
        else:
            self._placeholder_image(path)

        return path


class RCloneUploader:
    """Upload files using rclone and remove them locally."""

    def __init__(self, remote: Optional[str] = None):
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
            return

        try:
            subprocess.check_call(["rclone", "copy", filepath, self.remote])
            print(f"[RClone] Uploaded {filepath}")
        except Exception as exc:
            print(f"[RClone] Failed to upload {filepath}: {exc}")
        finally:
            pass


class CastlesAndCansGame:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.state = GameState.WAITING_START
        self.hw = HardwareInterface()
        self.current_team = None
        self.completed_targets = {Team.RED: set(), Team.GREEN: set()}
        self.current_target = {Team.RED: None, Team.GREEN: None}
        self.awaiting_tunnel = False
        self.prev_status = ""
        self.camera = CameraInterface()
        self.drive = RCloneUploader(os.environ.get("RCLONE_REMOTE"))
        self.chug_photo = None
        self.pressure_hits = {ch: 0 for ch in PRESSURE_CHANNELS}
        self._pressure_state = {ch: False for ch in PRESSURE_CHANNELS}
        self.watchtower_active = False
        self.setup_ui()
        # Bind all key events so they register regardless of focus
        self.root.bind_all('<Key>', self.handle_key)
        self.ball_in_play = False

        # Hook up GPIO callbacks for tunnel and ball return sensors
        if self.hw.available:
            try:
                GPIO.add_event_detect(
                    IR_TUNNEL_ENTRY,
                    GPIO.RISING,
                    callback=self._gpio_tunnel,
                    bouncetime=200,
                )
                GPIO.add_event_detect(
                    IR_BALL_RETURN,
                    GPIO.RISING,
                    callback=self._gpio_return,
                    bouncetime=200,
                )
                GPIO.add_event_detect(
                    IR_TARGET_1,
                    GPIO.RISING,
                    callback=self._gpio_target1,
                    bouncetime=200,
                )
                GPIO.add_event_detect(
                    BUTTON_START,
                    GPIO.RISING,
                    callback=self._gpio_start,
                    bouncetime=300,
                )
                GPIO.add_event_detect(

                    BUTTON_FORCE_TURN,
                    GPIO.RISING,
                    callback=self._gpio_force,
                    bouncetime=300,
                )
                GPIO.add_event_detect(
                    BUTTON_RED_DISPENSE,
                    GPIO.RISING,
                    callback=self._gpio_dispense_red,
                    bouncetime=300,
                )
                GPIO.add_event_detect(
                    BUTTON_GREEN_DISPENSE,
                    GPIO.RISING,
                    callback=self._gpio_dispense_green,
                    bouncetime=300,
                )
            except Exception as exc:
                print(f"[GPIO] Failed to add event detection: {exc}")

        # Start background polling for pressure sensors
        threading.Thread(target=self._poll_pressure_sensors, daemon=True).start()

    def _log(self, message: str):
        """Helper to print debug messages with a consistent prefix."""
        print(f"[Game] {message}")


    def choose_next_target(self, team: Team) -> Optional[int]:
        remaining = [t for t in range(1, NUM_TARGETS + 1) if t not in self.completed_targets[team]]
        return random.choice(remaining) if remaining else None


    def setup_ui(self):
        self.root.title("Castles & Cans")
        self.root.geometry("800x480")
        self.root.configure(bg=BG_COLOR)

        self.status_label = tk.Label(
            self.root,
            text="Press START",
            font=TITLE_FONT,
            fg=FG_COLOR,
            bg=BG_COLOR,
        )
        self.status_label.pack(pady=20, expand=True, fill=tk.BOTH)

        button_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.start_button = tk.Button(
            button_frame,
            text="Start / Reset",
            command=self.start_game,
            font=BUTTON_FONT,
            bg=BUTTON_BG,
            fg="white",
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.force_next_button = tk.Button(
            button_frame,
            text="Force Next Turn",
            command=self.next_turn,
            font=BUTTON_FONT,
            bg=BUTTON_BG,
            fg="white",
        )
        self.force_next_button.pack(side=tk.LEFT, padx=5)

        self.dispense_red = tk.Button(
            button_frame,
            text="Dispense Red",
            command=lambda: self.dispense_beer(Team.RED),
            font=BUTTON_FONT,
            bg="firebrick4",
            fg="white",
        )
        self.dispense_red.pack(side=tk.LEFT, padx=5)

        self.dispense_green = tk.Button(
            button_frame,
            text="Dispense Green",
            command=lambda: self.dispense_beer(Team.GREEN),
            font=BUTTON_FONT,
            bg="dark green",
            fg="white",
        )
        self.dispense_green.pack(side=tk.LEFT, padx=5)
        button_frame.pack(pady=10)

        self.progress_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.progress_labels = []
        for _ in range(NUM_TARGETS):
            lbl = tk.Label(
                self.progress_frame,
                text="○",
                font=PROGRESS_FONT,
                bg=BG_COLOR,
                fg=FG_COLOR,
            )
            lbl.pack(side=tk.LEFT, padx=4)
            self.progress_labels.append(lbl)
        self.progress_frame.pack(pady=5)

        self.target_label = tk.Label(
            self.root,
            text="",
            font=LABEL_FONT,
            fg=FG_COLOR,
            bg=BG_COLOR,
        )
        self.target_label.pack(pady=5)



        # Fullscreen overlay for photos with centered text
        self.overlay = tk.Frame(self.root, bg=BG_COLOR)
        self.overlay_image = tk.Label(self.overlay, bg=BG_COLOR)
        self.overlay_image.pack(fill=tk.BOTH, expand=True)
        self.overlay_text = tk.Label(
            self.overlay,
            text="",
            font=TITLE_FONT,
            fg=FG_COLOR,
            bg=BG_COLOR,
        )
        self.overlay_text.place(relx=0.5, rely=0.5, anchor="center")
        self.overlay.place_forget()
        self._anim_id = None

        # Ensure key events go to the root window
        self.root.focus_set()

    def start_game(self):
        self._log("Game started - flipping coin")
        self.hw.reset_servos()
        self.state = GameState.COIN_FLIP
        self.status_label.config(text="Flipping coin...")
        self.target_label.config(text="")
        self.hide_overlay()
        self.chug_photo = None
        self.ball_in_play = False
        self.completed_targets = {Team.RED: set(), Team.GREEN: set()}
        self.current_target = {Team.RED: None, Team.GREEN: None}
        self.watchtower_active = False
        self.hw.rotate_servo(SERVO_3, 90)  # reset watchtower
        self.hw.set_theme_lighting(None)
        # choose initial targets
        for team in Team:
            self.current_target[team] = self.choose_next_target(team)
        self.hw.restore_targets(Team.RED, 0)
        self.hw.restore_targets(Team.GREEN, 0)
        self.root.after(1000, self.finish_coin_flip)

    def finish_coin_flip(self):
        self.current_team = random.choice([Team.RED, Team.GREEN])
        self._log(f"{self.current_team.value} won the coin flip")
        self.status_label.config(
            text=f"{self.current_team.value} starts - hit target {self.current_target[self.current_team]}"
        )
        self.hw.set_theme_lighting(self.current_team)
        self.hw.restore_targets(self.current_team, len(self.completed_targets[self.current_team]))
        self.state = GameState.PLAYER_TURN
        self.update_progress()

    def hit_target(self, target: int):
        """Register a target hit. Always output the hardware event.

        Progress only advances when the game is in ``PLAYER_TURN`` state and
        the correct target for the current team is hit. Other hits merely show a
        message so key presses are visible when testing.
        """
        self._log(f"Target {target} hit")
        self.hw.hit_target(target)
        self.capture_image("hit")

        if self.state != GameState.PLAYER_TURN:
            # Show feedback even if the hit occurs at the wrong time
            self.status_label.config(text=f"Target {target} hit (not your turn)")
            return

        if target == self.current_target[self.current_team]:
            self.complete_target(target)
        else:
            self.hw.play_sound(SoundEffect.NEUTRAL_HIT)
            self.status_label.config(text=f"Target {target} hit out of order - await tunnel")
            self.awaiting_tunnel = False
            self.state = GameState.AWAITING_TUNNEL

    def complete_target(self, target: int):
        """Mark the target complete and prepare for the tunnel."""
        self._log(f"Target {target} completed by {self.current_team.value}")
        self.hw.play_sound(SoundEffect.TARGET_HIT)
        color = LedColor.RED if self.current_team == Team.RED else LedColor.GREEN
        self.hw.set_target_led(target, color)
        self.completed_targets[self.current_team].add(target)
        self.update_progress()
        if len(self.completed_targets[self.current_team]) >= NUM_TARGETS:
            self.win_game()
            return
        self.current_target[self.current_team] = self.choose_next_target(self.current_team)
        self.status_label.config(text=f"Target {target} hit! Await tunnel")
        self.state = GameState.AWAITING_TUNNEL
        self.awaiting_tunnel = True

    def win_game(self):
        """Handle a victory for the current team."""
        self._log(f"{self.current_team.value} wins the game")
        self.state = GameState.GAME_OVER
        self.ball_in_play = False
        self.status_label.config(text=f"{self.current_team.value} WINS!")
        self.hw.play_sound(SoundEffect.VICTORY)
        self.hw.drop_gate()
        self.hw.play_sound(SoundEffect.GATE_BREACH)
        self.hw.raise_pong_platform()
        self.hw.set_theme_lighting(None)

    def start_chug_phase(self):
        """Begin the chug phase once the ball launches."""
        self._log("Chug phase started")
        self.state = GameState.CHUG
        self.hw.start_chug(self.current_team)
        self.hw.play_sound(SoundEffect.CHUG_START)
        self.status_label.config(text=f"{self.current_team.value} CHUG!")
        # Capture a chug photo after a short delay without blocking
        self.root.after(2000, lambda: self.capture_image('chug', show=False, store_attr='chug_photo'))

    def end_chug_phase(self):
        self._log("Chug phase ended")
        self.hw.play_sound(SoundEffect.CHUG_STOP)
        self.hw.stop_chug(self.current_team)
        self.next_turn()

    def launch_ball(self):
        """Fire the plunger when the game is ready."""
        if self.state != GameState.AWAITING_LAUNCH:
            return
        self._log("Ball launched")
        self.hw.launch_plunger()
        self.ball_in_play = True
        if self.awaiting_tunnel:
            self.start_chug_phase()
        else:
            self.state = GameState.BALL_LAUNCHED
            self.status_label.config(text="Ball launched")
        self.hide_overlay()

    def tunnel_triggered(self):
        """Handle the ball entering the tunnel."""
        if self.state not in (
            GameState.AWAITING_TUNNEL,
            GameState.BALL_LAUNCHED,
            GameState.PLAYER_TURN,
        ):
            return

        self.hw.activate_tunnel(1)
        self._log("Tunnel triggered")
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
            self._log("Ready to launch")
            self.status_label.config(text="Ready to launch - press L")

    def dispense_beer(self, team: Team):
        self._log(f"Dispense beer for {team.value}")
        self.prev_status = self.status_label.cget("text")
        self.status_label.config(text=f"Dispensing beer for {team.value}")
        self.hw.play_sound(SoundEffect.DISPENSE)
        self.hw.dispense(team)
        self.root.after(2000, lambda: self.status_label.config(text=self.prev_status))

    def clear_tube(self):
        """Run the fan to clear the ball return tube."""
        self._log("Clearing tube")
        self.prev_status = self.status_label.cget("text")
        self.status_label.config(text="Clearing tube...")
        self.hw.blow_fan()
        self.root.after(5000, lambda: self.status_label.config(text=self.prev_status))

    def ball_returned(self):
        self._log("Ball returned")
        if self.state == GameState.CHUG:
            self.hw.play_sound(SoundEffect.CHUG_STOP)
            self.hw.stop_chug(self.current_team)
            self.status_label.config(text="Stop chugging")
            self.ball_in_play = False
            if self.chug_photo:
                self.show_overlay(self.chug_photo, "")
            if self.state != GameState.GAME_OVER:
                self.root.after(2000, self.next_turn)
        elif self.ball_in_play:
            self.status_label.config(text="Ball returned")
            self.ball_in_play = False
            if self.state != GameState.GAME_OVER:
                self.root.after(1000, self.next_turn)

    def next_turn(self):
        if self.current_team is None:
            return
        self._log("Switching turn")
        self.current_team = Team.GREEN if self.current_team == Team.RED else Team.RED
        self.current_target[self.current_team] = self.choose_next_target(self.current_team)
        self.status_label.config(
            text=f"{self.current_team.value} turn - hit target {self.current_target[self.current_team]}"
        )
        self.hw.set_theme_lighting(self.current_team)
        self.hw.restore_targets(self.current_team, len(self.completed_targets[self.current_team]))
        self.update_progress()
        self.ball_in_play = False
        self.awaiting_tunnel = False
        self.chug_photo = None
        self.hide_overlay()
        self.state = GameState.PLAYER_TURN

    def update_progress(self):
        hits = len(self.completed_targets[self.current_team])
        for i, lbl in enumerate(self.progress_labels):
            if i < hits:
                color = 'red' if self.current_team == Team.RED else 'green'
                lbl.config(text='●', fg=color)
            else:
                lbl.config(text='○', fg=FG_COLOR)
        next_t = self.current_target[self.current_team]
        self.target_label.config(text=f"Next target: {next_t if next_t else '-'}")

    def show_overlay(self, photo, text: str):
        """Display a fullscreen image with optional text."""
        self.overlay_image.config(image=photo)
        self.overlay_image.image = photo
        self.overlay_text.config(text=text)
        if self._anim_id:
            self.root.after_cancel(self._anim_id)
        self.overlay.place(x=0, y=self.root.winfo_height(), relwidth=1, relheight=1)
        self.overlay_text.lift()
        self._anim_id = None
        self._slide_overlay(0)

    def _slide_overlay(self, target_y: int, duration: int = 400):
        """Smoothly slide the overlay to ``target_y`` over ``duration`` ms."""
        start_y = self.overlay.winfo_y()
        distance = target_y - start_y
        steps = max(1, int(duration / 16))
        step = distance / steps

        def animate(count=0):
            y = start_y + step * count
            self.overlay.place(y=int(y), relwidth=1, relheight=1)
            if count < steps:
                self._anim_id = self.root.after(16, animate, count + 1)
            else:
                self.overlay.place(y=target_y, relwidth=1, relheight=1)
                if target_y >= self.root.winfo_height():
                    self.overlay.place_forget()
                self._anim_id = None

        animate()

    def hide_overlay(self):
        """Slide the overlay off the screen."""
        if self.overlay.winfo_ismapped():
            if self._anim_id:
                self.root.after_cancel(self._anim_id)
                self._anim_id = None
            self._slide_overlay(self.root.winfo_height())

    def capture_image(self, prefix: str, show: bool = True, store_attr: Optional[str] = None):
        """Capture an image asynchronously and optionally show it."""

        def worker():
            path = self.camera.capture_image(prefix)
            photo = None
            if Image and ImageTk:
                try:
                    img = Image.open(path)
                    img = img.resize((800, 480))
                    photo = ImageTk.PhotoImage(img)
                except Exception as exc:
                    print(f"Failed to load image {path}: {exc}")
            else:
                print("[Init] Pillow not available - skipping image preview")

            self.drive.upload(path)
            if store_attr is not None:
                setattr(self, store_attr, photo)
            if show and photo:
                self.root.after(0, lambda: [self.show_overlay(photo, ""), self.root.after(3000, self.hide_overlay)])

        threading.Thread(target=worker, daemon=True).start()

    # GPIO event callbacks run in a background thread; schedule on the Tk loop
    def _gpio_tunnel(self, channel):
        self.root.after(0, self.tunnel_triggered)

    def _gpio_return(self, channel):
        self.root.after(0, self.ball_returned)

    def _gpio_target1(self, channel):
        self.root.after(0, self.watchtower_ir_triggered)

    def _gpio_start(self, channel):
        self.root.after(0, self.start_game)

    def _gpio_force(self, channel):
        self.root.after(0, self.next_turn)

    def _gpio_dispense_red(self, channel):
        self.root.after(0, lambda: self.dispense_beer(Team.RED))

    def _gpio_dispense_green(self, channel):
        self.root.after(0, lambda: self.dispense_beer(Team.GREEN))

    def _poll_pressure_sensors(self):
        """Continuously check the pressure sensors for hits."""
        while True:
            for ch in PRESSURE_CHANNELS:
                value = self.hw.read_adc(ch)
                active = value > self.hw.pressure_sensitivity
                if active and not self._pressure_state[ch]:
                    self._pressure_state[ch] = True
                    self.pressure_hits[ch] += 1
                    print(f"[Pressure] Registered hit on channel {ch}")
                    if ch == 0:
                        self.root.after(0, self.watchtower_pressure_hit)
                elif not active and self._pressure_state[ch]:
                    self._pressure_state[ch] = False
            time.sleep(0.05)

    def watchtower_pressure_hit(self):
        if (
            self.state == GameState.PLAYER_TURN
            and self.current_target[self.current_team] == 1
            and not self.watchtower_active
        ):
            self._log("Watchtower pressure hit")
            self.watchtower_active = True
            self.status_label.config(text="Watchtower struck!")
            # Rotate servo 40 degrees counterclockwise from centre (90 -> 50)
            self.hw.rotate_servo(SERVO_3, 50)

    def watchtower_ir_triggered(self):
        if self.watchtower_active and self.current_target[self.current_team] == 1:
            self._log("Watchtower IR complete")
            self.hw.rotate_servo(SERVO_3, 90)
            self.watchtower_active = False
            self.complete_target(1)

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
        elif key in ['1', '2', '3', '4', '5', '6', '7']:
            self.hit_target(int(key))
        elif key == 'y':
            self.watchtower_ir_triggered()
        elif key == 't':
            self.tunnel_triggered()
        elif key == 'b':
            self.ball_returned()
        elif key == 'l':
            self.launch_ball()
        elif key == 'f':
            self.clear_tube()


if __name__ == "__main__":
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"[Error] Tk initialization failed: {exc}")
        sys.exit(1)
    game = CastlesAndCansGame(root)
    root.mainloop()
