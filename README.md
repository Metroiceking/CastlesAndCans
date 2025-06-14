# Castles & Cans

This repository contains an early prototype of **Castles & Cans**, an interactive castle-themed drinking game powered by a Raspberry Pi.

The game uses a touchscreen user interface and communicates with physical components such as sensors, lights and motors. Two teams (Red and Green) compete by hitting targets and triggering challenges.

At this stage the project includes a simple Python program (`src/game.py`) implementing the basic UI and placeholder hardware actions.

## Running

Ensure Python 3 with Tkinter is installed. Launch the prototype with:

```bash
python3 src/game.py
```

This will open a window demonstrating the UI flow: start/reset, coin flip and alternating turns. The window displays which target is currently required along with each team's progress. Targets must be hit in order; hitting the wrong target simply plays a neutral effect. After a successful hit the tunnel trigger starts a short countdown, launches the ball back and instructs the thrower to chug until the ball returns.

### Keyboard controls

The prototype uses keyboard keys to mimic hardware buttons:

- **s** – Start or reset the game
- **n** – Force next turn
- **r** – Dispense beer for the Red team
- **g** – Dispense beer for the Green team
- **1**..**5** – Trigger target sensors (progresses only if the next target is hit while the ball is in play)
- **p** – Launch ball with the plunger
- **b** – Signal that the ball returned
- **t** – Tunnel sensor triggered

Team progress is stored separately, and the hardware is instructed to restore
each side's targets whenever turns change.

A missed shot automatically ends the turn once the ball is returned.

Hardware-specific functions are still implemented as console print statements. Integrate with GPIO libraries on the Raspberry Pi as development continues.
