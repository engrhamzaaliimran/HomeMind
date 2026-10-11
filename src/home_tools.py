
import json
from pathlib import Path


# Location of the persistent house state
STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "home_state.json"


def get_home_state():
    """Read the current simulated house state."""

    with open(STATE_FILE, "r") as file:
        return json.load(file)


def set_temperature(room: str, temperature_c: float):
    """Set the target thermostat temperature of a room."""

    # Step 1: Load the current state
    state = get_home_state()

    # Step 2: Validate the requested room
    if room not in state or "target_temperature" not in state[room]:
        return {"success": False, "error": "Unknown thermostat"}

    # Step 3: Validate the temperature
    if not 10 <= temperature_c <= 30:
        return {"success": False, "error": "Temperature must be between 10 and 30°C"}

    # Step 4: Update the state
    state[room]["target_temperature"] = temperature_c

    # Step 5: Save the updated state
    with open(STATE_FILE, "w") as file:
        json.dump(state, file, indent=2)

    return {
        "success": True,
        "room": room,
        "target_temperature": temperature_c
    }


def set_light(room: str, on: bool):
    """Turn a room's light on or off."""

    state = get_home_state()

    if room not in state or "light" not in state[room]:
        return {"success": False, "error": "Unknown light"}

    if not isinstance(on, bool):
        return {"success": False, "error": "on must be a boolean"}

    state[room]["light"] = on

    with open(STATE_FILE, "w") as file:
        json.dump(state, file, indent=2)

    return {"success": True, "room": room, "light": on}


def set_door_lock(door: str, locked: bool):
    """Lock or unlock a door."""

    state = get_home_state()

    if door not in state or "locked" not in state[door]:
        return {"success": False, "error": "Unknown door"}

    if not isinstance(locked, bool):
        return {"success": False, "error": "locked must be a boolean"}

    state[door]["locked"] = locked

    with open(STATE_FILE, "w") as file:
        json.dump(state, file, indent=2)

    return {"success": True, "door": door, "locked": locked}
