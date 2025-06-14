# Game logic and UI for Castles & Cans
# Placeholder implementation for Raspberry Pi hardware integration

import random
import tkinter as tk
from enum import Enum, auto


class Team(Enum):
    RED = 'Red'
    GREEN = 'Green'


class GameState(Enum):
    WAITING_START = auto()
    COIN_FLIP = auto()
    IN_PLAY = auto()
    BALL_IN_PLAY = auto()
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

    def raise_platform(self):
        print("[HW] RAISE_PONG_PLATFORM")


class CastlesAndCansGame:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.state = GameState.WAITING_START
        self.hw = HardwareInterface()
        self.current_team = None
        self.target_hits = {Team.RED: 0, Team.GREEN: 0}
        self.setup_ui()
        self.root.bind('<Key>', self.handle_key)
        self.ball_in_play = False

    def setup_ui(self):
        self.root.title("Castles & Cans")
        self.status_label = tk.Label(self.root, text="Press START", font=("Arial", 24))
        self.status_label.pack(pady=20)

        self.start_button = tk.Button(self.root, text="Start / Reset", command=self.start_game)
        self.start_button.pack(side=tk.LEFT, padx=10)

        self.force_next_button = tk.Button(self.root, text="Force Next Turn", command=self.next_turn)
        self.force_next_button.pack(side=tk.LEFT, padx=10)

        self.dispense_red = tk.Button(self.root, text="Dispense Red", command=lambda: self.hw.dispense(Team.RED))
        self.dispense_red.pack(side=tk.LEFT, padx=10)

        self.dispense_green = tk.Button(self.root, text="Dispense Green", command=lambda: self.hw.dispense(Team.GREEN))
        self.dispense_green.pack(side=tk.LEFT, padx=10)

        self.progress_frame = tk.Frame(self.root)
        self.progress_labels = []
        for _ in range(5):
            lbl = tk.Label(self.progress_frame, text="○", font=("Arial", 24))
            lbl.pack(side=tk.LEFT, padx=4)
            self.progress_labels.append(lbl)
        self.progress_frame.pack(pady=10)

        self.ball_label = tk.Label(self.root, text="", font=("Arial", 18))
        self.ball_label.pack(pady=5)

    def start_game(self):
        self.state = GameState.COIN_FLIP
        self.status_label.config(text="Flipping coin...")
        self.ball_label.config(text="")
        self.ball_in_play = False
        self.root.after(1000, self.finish_coin_flip)

    def finish_coin_flip(self):
        self.current_team = random.choice([Team.RED, Team.GREEN])
        self.status_label.config(text=f"{self.current_team.value} starts!")
        self.state = GameState.IN_PLAY
        self.update_progress()
        self.ball_label.config(text="Press 'p' to launch ball")

    def hit_target(self, target: int):
        self.hw.hit_target(target)
        self.target_hits[self.current_team] += 1
        self.update_progress()
        if self.target_hits[self.current_team] >= 5:
            self.start_chug_phase()

    def start_chug_phase(self):
        self.state = GameState.CHUG
        self.hw.start_chug(self.current_team)
        self.status_label.config(text=f"{self.current_team.value} CHUG!")
        self.root.after(5000, self.end_chug_phase)

    def end_chug_phase(self):
        self.hw.stop_chug(self.current_team)
        self.next_turn()

    def launch_ball(self):
        if self.state not in (GameState.IN_PLAY, GameState.BALL_IN_PLAY):
            return
        if not self.ball_in_play:
            self.hw.raise_platform()
            self.ball_in_play = True
            self.state = GameState.BALL_IN_PLAY
            self.ball_label.config(text="Ball launched - press 'b' when returned")

    def ball_returned(self):
        if self.ball_in_play:
            self.hw.activate_tunnel(1)
            self.ball_in_play = False
            self.state = GameState.IN_PLAY
            self.ball_label.config(text="Ball returned")

    def next_turn(self):
        if self.current_team is None:
            return
        self.target_hits[self.current_team] = 0
        self.current_team = Team.GREEN if self.current_team == Team.RED else Team.RED
        self.status_label.config(text=f"{self.current_team.value} turn")
        self.update_progress()
        self.ball_in_play = False
        self.ball_label.config(text="Press 'p' to launch ball")

    def update_progress(self):
        hits = self.target_hits[self.current_team]
        for i, lbl in enumerate(self.progress_labels):
            if i < hits:
                color = 'red' if self.current_team == Team.RED else 'green'
                lbl.config(text='●', fg=color)
            else:
                lbl.config(text='○', fg='black')

    def handle_key(self, event):
        key = event.keysym.lower()
        if key == 's':
            self.start_game()
        elif key == 'n':
            self.next_turn()
        elif key == 'r':
            self.hw.dispense(Team.RED)
        elif key == 'g':
            self.hw.dispense(Team.GREEN)
        elif key in ['1', '2', '3', '4', '5']:
            self.hit_target(int(key))
        elif key == 'b':
            self.ball_returned()
        elif key == 'd':
            self.hw.drop_gate()
        elif key == 'p':
            self.launch_ball()


if __name__ == "__main__":
    root = tk.Tk()
    game = CastlesAndCansGame(root)
    root.mainloop()
