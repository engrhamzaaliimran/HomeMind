
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from home_tools import (
    get_home_state,
    set_temperature,
    set_light,
    set_door_lock,
)


# Same model configuration as Stage 01
llm = ChatOllama(
    model="qwen3:1.7b",
    temperature=0,
    reasoning=False,
    num_predict=200,
)


# Convert our existing Python functions into LangChain tools
tools = [
    StructuredTool.from_function(func=get_home_state),
    StructuredTool.from_function(func=set_temperature),
    StructuredTool.from_function(func=set_light),
    StructuredTool.from_function(func=set_door_lock),
]


# Preserve the capability-first procedure from Stage 01


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

# system_prompt = f"""
# You are HomeMind, an intelligent smart-home assistant
# controlling a SIMULATED home.

# AVAILABLE TOOLS:
# {", ".join(tool.name for tool in tools)}

# MANDATORY DECISION PROCEDURE:

# STEP 1 - INTENT
# Identify the user's request using conversation history.

# STEP 2 - CAPABILITY CHECK
# Check whether an available tool can perform the action.
# If no matching tool exists, the action is UNAVAILABLE.
# Never invent tools or promise unsupported actions.

# STEP 3 - EXECUTION VERIFICATION
# Use the appropriate tool to execute supported actions.
# A tool request is NOT evidence of execution.
# Only report an action as completed when its tool result
# explicitly confirms success: true.
# If success is false, report the failure.
# Conversation history is NOT execution evidence.

# STEP 4 - RESPONSE
# For action requests, use:

# Capability: AVAILABLE or UNAVAILABLE
# Response: Your answer based on verified results.

# For state questions, use get_home_state.
# Never invent device readings, states, or execution results.
# Keep answers concise.
# """


agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
)


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

    # Display the actual tool requests and execution results
    for message in result["messages"][len(messages):]:

        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                print("\nTOOL REQUEST:", call["name"], call["args"])

        elif isinstance(message, ToolMessage):
            print("TOOL RESULT:", message.content)

    print("\nHomeMind:", result["messages"][-1].content)

    # Keep the last five complete user turns
    history = result["messages"]

    user_positions = [
        i for i, message in enumerate(history)
        if isinstance(message, HumanMessage)
    ]

    if len(user_positions) > MAX_TURNS:
        history = history[user_positions[-MAX_TURNS]:]
