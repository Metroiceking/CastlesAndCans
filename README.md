# Castles & Cans

This repository contains an early prototype of **Castles & Cans**, an interactive castle-themed drinking game powered by a Raspberry Pi.

The game uses a touchscreen user interface and communicates with physical components such as sensors, lights and motors. Two teams (Red and Green) compete by hitting targets and triggering challenges.

At this stage the project includes a simple Python program (`src/game.py`) implementing the basic UI and placeholder hardware actions.

## Running

Ensure Python 3 with Tkinter is installed. Launch the prototype with:

```bash
python3 src/game.py
```

The UI requires an X11 display. If no display is available the script will exit
with an error message. When running over SSH be sure to enable X forwarding or
attach a screen to the Pi.

The window now features a medieval-style colour scheme with parchment text on a
dark stone background. Photos captured by the Pi camera slide in from the bottom
to fill the entire screen with the status text overlaid in the centre. The layout
fits the 800×480 Pi touchscreen so previews no longer spill off the edges. The
photo overlay now animates smoothly with centred text, stays visible for three seconds
and hides automatically.

The game logic lives in `src/game.py`.  It drives the user interface and
simulated hardware while tracking each team's progress.  The program cycles
through a number of **states**:

* `WAITING_START` – initial idle state
* `COIN_FLIP` – choose the starting team
* `PLAYER_TURN` – wait for the team to hit its required target
* `AWAITING_TUNNEL` – target hit, waiting for the ball to enter the tunnel
* `AWAITING_LAUNCH` – tunnel triggered, countdown before launch
* `BALL_LAUNCHED` – ball launched but no chugging
* `CHUG` – active chug phase after a successful hit
* `GAME_OVER` – all targets complete

This will open a window demonstrating the UI flow: start/reset, coin flip and alternating turns. The window displays which randomly-chosen target is required along with each team's progress. Each team must complete all seven targets once. Hitting the wrong target simply plays a neutral effect. Once the proper target is cleared the game waits for the tunnel sensor. A couple of seconds after the tunnel triggers the screen shows **Ready to launch**. Press the launch key to fire the plunger. Chugging only begins once the ball is launched and stops when it is returned.

### Keyboard controls

The prototype uses keyboard keys to mimic hardware buttons:

- **s** – Start or reset the game
- **n** – Force next turn
- **r** – Dispense beer for the Red team (Servo 1 counterclockwise, opens the Red door)
- **g** – Dispense beer for the Green team (Servo 2 clockwise, opens the Green door)
- **1**..**7** – Trigger target sensors (registers a hit only when it matches the current team's assigned target)
- **y** – Simulate the IR sensor completing Target 1
- **l** – Launch the ball after the tunnel is triggered
- **b** – Signal that the ball returned
- **t** – Tunnel sensor triggered (prepares launch)
- **f** – Blow the fan for five seconds to clear the tube

Each team has its own beer door on the castle. The Red door is driven by **Servo 1** and the Green door by **Servo 2**. Pressing the matching dispense button or key opens that team's door for three seconds before closing it again.

When running on a Raspberry Pi with GPIO enabled, the IR sensors connected to
**IR_TUNNEL_ENTRY** (BCM 15) and **IR_BALL_RETURN** (BCM 14) automatically
trigger the same actions as the **t** and **b** keys.

Likewise the physical buttons are mapped to their keyboard equivalents:
the single Start/Reset button acts like **s**, the Force Next Turn button like
**n**, and the dispense buttons match **r** and **g**.  These buttons should
be wired between the Pi's 3.3 V rail and the respective GPIO pin; the
script enables the internal pull‑down resistors so a press registers as a
RISING edge.

Dispensing a beer moves the tap servos. Pressing the Red button opens the red door by rotating **Servo 1** 100° counterclockwise while the Green button opens the green door by spinning **Servo 2** 100° clockwise. Each servo automatically returns to centre after three seconds.

Servo positions are saved to `servo_state.json` whenever they move. On startup
and whenever a new game begins, the program checks this file and only moves each
servo back to its default 90° position if it wasn't already there. This helps
avoid sudden movements if the Pi loses power mid-game.

Team progress is stored separately, and the hardware is instructed to restore
each side's targets whenever turns change.

A missed shot automatically ends the turn once the ball is returned.

Basic GPIO support is now included using BCM pin numbering. When the script
detects the RPi.GPIO library it configures each pin as described below;
otherwise the hardware actions are simply printed for testing on other
systems.

### Camera captures and uploads

When a target is hit, the Pi camera snaps a photo that slides onto the screen while the game prepares to launch the ball. Another photo is taken a couple of seconds into the chug phase and displayed full screen when the ball returns. These images are automatically uploaded using **rclone** but remain in the `captures` directory for the rest of the session. Old captures are cleaned up whenever the program starts.

The script looks for either `libcamera-still` or `raspistill` to capture photos at **1280×720**. The `--immediate` option is used with `libcamera-still` to minimise shutter lag and photos are captured in a background thread so the UI remains responsive. If neither command is available the program creates placeholder images instead.

Set the environment variable `RCLONE_REMOTE` to the destination configured in rclone, for example `mydrive:CastlesAndCans`. If the variable is missing or rclone is not installed, uploads are skipped.

Only the Pillow package is required for displaying images:

```bash
pip install Pillow
```

The Pillow package must include ImageTk support. On some systems this requires the `python3-pil.imagetk` package or similar.

### RClone setup

1. Install rclone on the Pi. You can use `sudo apt install rclone` or follow the instructions on [rclone.org](https://rclone.org/install/).
2. Run `rclone config` and create a remote for Google Drive (or another provider). Note the remote name.
3. Create or choose a folder on your remote to store uploads.
4. Set `RCLONE_REMOTE` to `<remote>:<folder>` (for example `gdrive:CastlesAndCans`).
5. Run the prototype and check the console for `[RClone] Uploader configured for ...`.

### Pressure sensors

Four thin-film force sensors attach to the MCP3008 ADC on channels 0–3.  The
game polls these inputs in the background and logs a hit whenever the reading
exceeds a sensitivity threshold.  Hits are counted per channel for future
expansion.

Target 1 is a small watchtower. Hitting the front pressure sensor (channel 0)
rotates **Servo 3** 40° counterclockwise to reveal an infrared beam inside the
tower. When that beam (``IR_TARGET_1``) is broken, the target is marked
complete and the servo returns to its starting position.

Adjust `PRESSURE_SENSITIVITY` in `src/game.py` if the sensors are too sensitive
or not sensitive enough.

### Hardware actions

`HardwareInterface` in `src/game.py` abstracts every output the real game will
control.  When running on a desktop these methods simply print messages so the
logic can be tested without wiring anything up.  It also includes helper
functions for playing sounds and driving LEDs so the high-level logic stays the
same once real hardware is connected. The key actions are:


| Method | Purpose |
|--------|---------|
| `blow_fan(duration)` | Pulse the fan relay to clear the ball return tube |
| `start_chug(team)` and `stop_chug(team)` | Start or stop the chug phase |
| `hit_target(n)` | Flash lights or play a sound for target `n` |
| `drop_gate()` | Release the castle gate on victory |
| `dispense(team)` | Open the team's beer door (Servo 1 for Red, Servo 2 for Green) |
| `activate_tunnel(n)` | Indicate a ball has entered tunnel `n` |
| `launch_plunger()` | Fire the plunger to launch the ball |
| `restore_targets(team, hits)` | Reset physical targets to a team's progress |
| `play_sound(effect)` | Play an audio effect |
| `set_target_led(target, color)` | Change a target's indicator LED |
| `set_theme_lighting(team)` | Adjust theme lighting for the active team |
| `raise_pong_platform()` | Raise the pong platform on victory |

These helper methods allow the software to run headless or on different
hardware by adjusting only the implementation in one place.

### GPIO Pin Assignments

The table below lists the BCM GPIO pins used by the project. The Python script
initialises these pins automatically when RPi.GPIO is available.

| Component                | BCM Pin | Header Pin |
|--------------------------|---------|------------|
| RELAY_FAN                | 17      | 11         |
| RELAY_RED_DISPENSE       | 5       | 29         |
| RELAY_GREEN_DISPENSE     | 6       | 31         |
| RELAY_EXPANSION_1        | 13      | 33         |
| RELAY_EXPANSION_2        | 19      | 35         |
| RELAY_EXPANSION_3        | 26      | 37         |
| NEOPIXEL_PIN             | 18      | 12         |
| BUTTON_START/RESET       | 23      | 16         |
| BUTTON_FORCE_TURN        | 24      | 18         |
| BUTTON_RED_DISPENSE      | 20      | 38         |
| BUTTON_GREEN_DISPENSE    | 21      | 40         |
| IR_BALL_RETURN           | 14      | 8          |
| IR_TUNNEL_ENTRY          | 15      | 10         |
| IR_TARGET_1              | 0       | 27         |
| MCP3008_CLK              | 11      | 23         |
| MCP3008_MISO             | 9       | 21         |
| MCP3008_MOSI             | 10      | 19         |
| MCP3008_CS               | 8       | 24         |
| SERVO_1                  | 12      | 32         |
| SERVO_2                  | 16      | 36         |
| SERVO_3                  | 4       | 7          |
| SERVO_4                  | 3       | 5          |
| SERVO_5                  | 2       | 3          |
| SERVO_6                  | 27      | 13         |
| SERVO_7                  | 22      | 15         |
| SERVO_8                  | 7       | 26         |

