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
photo overlay now animates smoothly and hides automatically a couple of seconds
after appearing.

This will open a window demonstrating the UI flow: start/reset, coin flip and alternating turns. The window displays which target is currently required along with each team's progress. Targets must be hit in order; hitting the wrong target simply plays a neutral effect. Once the correct target is hit the game waits for the tunnel sensor. A couple of seconds after the tunnel triggers the screen shows **Ready to launch**. Press the launch key to fire the plunger. Chugging only begins once the ball is launched and stops when it is returned.

### Keyboard controls

The prototype uses keyboard keys to mimic hardware buttons:

- **s** – Start or reset the game
- **n** – Force next turn
- **r** – Dispense beer for the Red team
- **g** – Dispense beer for the Green team
- **1**..**5** – Trigger target sensors (progresses only if the next target in order is hit)
- **l** – Launch the ball after the tunnel is triggered
- **b** – Signal that the ball returned
- **t** – Tunnel sensor triggered (prepares launch)

Team progress is stored separately, and the hardware is instructed to restore
each side's targets whenever turns change.

A missed shot automatically ends the turn once the ball is returned.

Hardware-specific functions are still implemented as console print statements. Integrate with GPIO libraries on the Raspberry Pi as development continues.

### Camera captures and uploads

When a target is hit, the Pi camera snaps a photo that slides onto the screen while the game prepares to launch the ball. Another photo is taken a couple of seconds into the chug phase and displayed full screen when the ball returns. These images are automatically uploaded using **rclone** but remain in the `captures` directory for the rest of the session. Old captures are cleaned up whenever the program starts.

The script looks for either `libcamera-still` or `raspistill` to capture photos at **1280×720**. The `--immediate` option is used with `libcamera-still` to minimise shutter lag. If neither command is available the program creates placeholder images instead.

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
