"""Draw the tutor's current picture on the UNO Q's LED matrix.

The tutor (app/server.py) decides what to show and serves it at /api/led as an
8x13 grid of brightness values, 0 to 7. This app only fetches that grid a few
times a second and passes it to the microcontroller through the Bridge. All
the logic stays in the tutor, so the tutor also works without this app.

Based on the official example core-and-foundational/02-led-matrix/02-led-matrix-frame
in https://github.com/arduino/app-bricks-examples. NOT TESTED on a board yet:
check first that this app can reach the tutor (see CANDIDATES below).
"""
import json
import time
import urllib.request

import numpy as np
from arduino.app_utils import App, Bridge, Frame

# Where the tutor may be reachable from. If App Lab runs this code in a
# container, 127.0.0.1 is the container itself: start the tutor with
# --host 0.0.0.0 so one of the other addresses works.
CANDIDATES = ["http://127.0.0.1:8090", "http://host.docker.internal:8090", "http://172.17.0.1:8090"]

state = {"base": None, "version": None, "next_search": 0.0}


def fetch(base):
    with urllib.request.urlopen(base + "/api/led", timeout=2) as response:
        return json.loads(response.read())


def find_tutor():
    for base in CANDIDATES:
        try:
            fetch(base)
            print(f"Tutor found at {base}")
            return base
        except Exception:   # also a half-started tutor (bad HTTP, bad JSON): try the next one
            continue
    print("Tutor not reachable. Is app/server.py running (with --host 0.0.0.0)?")
    return None


def draw(grid):
    Bridge.call("draw", Frame(np.array(grid, dtype=np.uint8)).to_board_bytes())


def loop():
    now = time.time()
    if state["base"] is None:
        if now >= state["next_search"]:
            state["base"] = find_tutor()
            state["next_search"] = now + 5
        time.sleep(0.3)
        return
    try:
        view = fetch(state["base"])
    except Exception:   # an error here must never stop the loop: look for the tutor again
        state["base"], state["version"] = None, None
        return
    if view["version"] != state["version"]:   # only redraw when the picture changes
        try:
            draw(view["frame"])
            state["version"] = view["version"]
        except Exception as error:   # try again on the next pass
            print(f"Could not draw: {type(error).__name__}: {error}")
    time.sleep(0.3)


App.run(user_loop=loop)
