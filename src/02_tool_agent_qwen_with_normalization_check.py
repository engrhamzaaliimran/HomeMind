"""HomeMind Stage 02.1: Python device-ID checks before tool execution.

Drop only this file into the existing HomeMind/src folder and run:
    python src/02_tool_agent_qwen_with_normalization_check.py

Requires your existing src/home_tools.py and data/home_state.json. This
experiment keeps the original Stage 02 model, system prompt, four tool names,
argument signatures and five-turn RAM history unchanged. No fuzzy guessing.
The original src/02_tool_agent_qwen.py is not modified.

Safety fix: parallel multi-device tool calls are serialized in this process.
This prevents two tools from rewriting the same JSON file concurrently.
"""

# STAGE 02.1 CHANGE LOG (relative to 02_tool_agent_qwen.py)
# WHY: Stage 02 evaluation found valid actions failing when Qwen generated
#       device names such as "living room" instead of the JSON ID "living_room".
# ADDED: A small deterministic ID resolver, structured rejection messages,
#        and three checked wrappers around the existing write functions.
# UNCHANGED: Qwen settings, complete system prompt, four tool names/schemas,
#            the original home_tools.py, and the five-turn RAM history.
# SCOPE: Only fix known device-ID spelling/alias errors, NOT intent errors,
#        unsupported capabilities, ambiguous requests, or hallucinated claims.
#        Python executes immediately after a trusted match; no second LLM call.
# ADDITIONAL FIX: Lock JSON access across parallel LangChain tool calls.
# WHY: Multi-device requests could overlap read/modify/write operations,
#      corrupting home_state.json and crashing the evaluation.

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# NEW: Built-in regex for converting separators to a canonical underscore.
# No third-party fuzzy matching or embedding library is used.
import re
from threading import RLock

from home_tools import (
    get_home_state as _read_home_state,
    set_temperature,
    set_light,
    set_door_lock,
)

# NEW: Multiple tool calls in a single AIMessage may run concurrently.
# The original home_tools.py functions read and rewrite the SAME JSON file.
# A re-entrant lock ensures a complete read -> validate -> modify -> write
# finishes before another HomeMind tool accesses that file.
# This protects ONE running Python process; it is not a multi-process file lock.
_HOME_STATE_LOCK = RLock()


def get_home_state():
    """Read the current simulated house state."""
    # Reading must also be protected: another thread may be rewriting JSON.
    with _HOME_STATE_LOCK:
        return _read_home_state()


# NEW: Explicit aliases for genuinely equivalent names that separator
# normalization alone cannot recover (e.g. "livingroom" or "front").
# WHY: A small reviewed dictionary is deterministic and avoids mapping an
# unrelated device name to a real device by approximate string similarity.
# Normal space / hyphen variants are handled separately below.
ROOM_ALIASES = {
    "livingroom": "living_room",
    "bed_room": "bedroom",
}
DOOR_ALIASES = {
    "front": "front_door",
}


# NEW: Validate the model-generated device argument *before* the write tool.
# WHY: A plausible device string is not enough; it must identify a real device
# that exposes the requested property (thermostat, light, or door lock).
# Example: "living room" + capability="light" -> "living_room".
def resolve_device_id(proposed_id: str, capability: str):
    """Return (resolved_id, was_normalized, valid_ids); otherwise (None, False, ids).

    Devices are valid only if their current state has the requested capability.
    No fuzzy matching, no guessing, and no silent fallbacks.
    """
    if capability not in ("target_temperature", "light", "locked"):
        raise ValueError("Unknown capability")

    # Read the current device registry from JSON instead of hard-coding IDs.
    # This prevents a valid light ID from being accepted as a thermostat ID.
    state = get_home_state()
    valid_ids = sorted(
        device_id for device_id, settings in state.items()
        if isinstance(settings, dict) and capability in settings
    )
    if not isinstance(proposed_id, str):
        return None, False, valid_ids

    # Case, leading/trailing whitespace, spaces and hyphens are spelling variants.
    # Do not remove arbitrary characters or use string similarity.
    # e.g. " Living-Room " -> "living_room"; "livng rom" stays invalid.
    candidate = re.sub(r"[\s-]+", "_", proposed_id.strip().casefold())
    aliases = DOOR_ALIASES if capability == "locked" else ROOM_ALIASES
    canonical = aliases.get(candidate, candidate)
    # Unknown IDs are rejected; NEVER take the "closest" match automatically.
    if canonical not in valid_ids:
        return None, False, valid_ids
    return canonical, canonical != proposed_id, valid_ids


# NEW: Return a structured failure rather than forwarding a bad argument.
# WHY: Qwen can tell the user the device is unknown and ask for clarification;
# critically, no write happens and no successful action may be claimed.
def invalid_device_error(device_id, capability, valid_ids):
    """Structured error for the LLM. No write has been attempted."""
    return {
        "success": False,
        "error": "INVALID_DEVICE_ID",
        "requested_device": device_id,
        "capability": capability,
        "available_devices": valid_ids,
        "message": "Device not found for this capability; no action was executed. Ask the user to clarify the device. Do not claim success.",
    }


# NEW: Add a small audit record only when Python corrected a device ID.
# WHY: Evaluation can distinguish a correct model argument from one repaired
# by Python. The original tool's success/failure response is preserved.
def with_normalization_record(result, original, canonical, was_normalized):
    # Keep the original home_tools result structure; add audit evidence only
    # when a spelling variant was actually corrected.
    if was_normalized:
        return {**result, "device_id_normalization": {"from": original, "to": canonical}}
    return result


# NEW: These three wrappers are the only change in the execution path.
# Each checks a device ID, calls the UNCHANGED original Python function on a
# trusted match, and returns the real execution result to LangChain/Qwen.
# All other input validation (e.g. temperature range, boolean flags) remains
# the responsibility of home_tools.py, as in the Stage 02 baseline.
def set_temperature_checked(room: str, temperature_c: float):
    """Set the target thermostat temperature of a room."""
    # Hold the lock across validation AND the original read/modify/write.
    # Locking only the normalization step would still allow corrupted JSON.
    with _HOME_STATE_LOCK:
        device, changed, valid = resolve_device_id(room, "target_temperature")
        if device is None:
            return invalid_device_error(room, "target_temperature", valid)
        return with_normalization_record(
            set_temperature(room=device, temperature_c=temperature_c), room, device, changed
        )


def set_light_checked(room: str, on: bool):
    """Turn a room's light on or off."""
    # Serialize the entire device update with other read/write tool calls.
    with _HOME_STATE_LOCK:
        device, changed, valid = resolve_device_id(room, "light")
        if device is None:
            return invalid_device_error(room, "light", valid)
        return with_normalization_record(set_light(room=device, on=on), room, device, changed)


def set_door_lock_checked(door: str, locked: bool):
    """Lock or unlock a door."""
    # Serialize door updates too; they share the same state JSON with rooms.
    with _HOME_STATE_LOCK:
        device, changed, valid = resolve_device_id(door, "locked")
        if device is None:
            return invalid_device_error(door, "locked", valid)
        return with_normalization_record(
            set_door_lock(door=device, locked=locked), door, device, changed
        )


# Identical model configuration to Stage 02.
llm = ChatOllama(
    model="qwen3:1.7b",
    temperature=0,
    reasoning=False,
    num_predict=200,
)

# CHANGE: Register the checked wrappers under the SAME public LangChain tool
# names and argument fields. Therefore Qwen still calls set_light(room, on),
# while the wrapper normalizes room before calling home_tools.set_light().
# get_home_state has no device-ID argument, so its read-only schema stays
# unchanged; a lock was added to prevent reading partially written JSON.
# The model sees the same system prompt and tool descriptions as in Stage 02.
tools = [
    StructuredTool.from_function(func=get_home_state),
    StructuredTool.from_function(func=set_temperature_checked, name="set_temperature"),
    StructuredTool.from_function(func=set_light_checked, name="set_light"),
    StructuredTool.from_function(func=set_door_lock_checked, name="set_door_lock"),
]


# The following system prompt is intentionally copied VERBATIM from Stage 02.
# This permits a meaningful before/after comparison of the Python tool layer.
system_prompt = f"""
You are HomeMind, an intelligent assistant controlling a
SIMULATED smart home.

AVAILABLE TOOLS:
{", ".join(tool.name for tool in tools)}

You can also answer general knowledge questions without tools.

MANDATORY DECISION PROCEDURE:

STEP 1 - UNDERSTAND
Identify the user's intent using conversation history.

- General question: Answer normally without tools.
- Home state question: Call get_home_state.
- Home control request: Identify the appropriate tool.
- Ambiguous request: Ask for clarification.

STEP 2 - CAPABILITY CHECK
Before controlling a device, check available tools.

If a matching tool exists, use it.
If no matching tool exists, explain the limitation.
Never invent devices, tools, or capabilities.

STEP 3 - EXECUTE AND VERIFY
Use actual structured tool calls to perform actions.

A tool request is NOT evidence of execution.
An action is completed ONLY when its tool result
explicitly confirms success=true.

If a tool returns success=false, report the actual error.
Never invent reasons for a failed tool call.

For state questions, use get_home_state.
Its returned JSON describes the actual simulated state.

IMPORTANT:
target_temperature is the thermostat SETPOINT,
not a measured room temperature.

Previous assistant statements are not execution evidence.

STEP 4 - RESPOND
Answer naturally and concisely.

For successful actions, confirm only verified changes.
For failed actions, report the failure.
For unsupported actions, explain what is unavailable.
For general questions, answer normally.

Never print function names or JSON as a substitute
for actually calling a tool.

ONE-SHOT TOOL-CALLING EXAMPLE:

User:
Turn on the bedroom light.

Correct function call representation:

{{
  "name": "set_light",
  "arguments": {{
    "room": "bedroom",
    "on": true
  }}
}}

IMPORTANT:
This JSON illustrates the tool name and arguments.
Do NOT print it as your answer.
Instead, generate a REAL structured tool call using
the available tool-calling interface.

After the tool executes, suppose the result is:

{{
  "success": true,
  "room": "bedroom",
  "light": true
}}

Your final response should be:
"The bedroom light has been turned on."

If execution fails, do NOT claim success.

END OF EXAMPLE.

Always prioritize actual tool results over conversation
history when reporting whether actions succeeded.
"""

# UNCHANGED: LangChain agent construction; Python validation is inside the
# registered tools, not in a second LLM call or a new orchestrator.
agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)

# UNCHANGED: Last five complete user turns remain in RAM; SQLite / semantic
# memory is deliberately out of scope until the reliability issues are fixed.
history = []
MAX_TURNS = 5

while True:
    command = input("\nSmart-home command (q to quit): ").strip()
    if command.lower() == "q":
        break
    if not command:
        continue

    messages = history + [HumanMessage(content=command)]
    result = agent.invoke({"messages": messages})

    # UNCHANGED: Print actual AIMessage.tool_calls and ToolMessage results.
    # If Python repairs a device name, the ToolMessage includes
    # device_id_normalization so it is visible during debugging.
    for message in result["messages"][len(messages):]:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                print("\nTOOL REQUEST:", call["name"], call["args"])
        elif isinstance(message, ToolMessage):
            print("TOOL RESULT:", message.content)
    print("\nHomeMind:", result["messages"][-1].content)

    history = result["messages"]
    user_positions = [i for i, message in enumerate(history) if isinstance(message, HumanMessage)]
    if len(user_positions) > MAX_TURNS:
        history = history[user_positions[-MAX_TURNS]:]