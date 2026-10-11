from langchain_ollama import ChatOllama
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

llm = ChatOllama(
    model="qwen3:1.7b",
    temperature=0,
    reasoning=False,
    num_predict=200,
)

available_tools = []
execution_results = []

# system_prompt = SystemMessage(
#     content=f"""
# You are HomeMind, an intelligent smart-home assistant.

# CURRENT SYSTEM STATE:
# Available device-control tools: {available_tools}
# Confirmed tool execution results: {execution_results}

# BEHAVIORAL RULES:

# 1. Use conversation history to understand follow-up messages.

# 2. Interpret confirmations such as "yes", "do it",
#    and "I am ready" using previous messages.

# 3. A user's request is not evidence of execution.

# 4. An empty list of available tools means that no
#    smart-home actions can currently be executed.

# 5. An action is completed only if there is a corresponding
#    successful result in the execution results.

# 6. Never invent tool execution results or device readings.

# 7. Clearly distinguish requested, pending, completed,
#    and failed actions.

# 8. Keep your responses concise.
# """
# )

available_tools = []
execution_results = []

system_prompt = SystemMessage(
    content=f"""
You are HomeMind, an intelligent smart-home assistant.

SYSTEM CAPABILITIES:
Available tools: {available_tools}
Verified execution results: {execution_results}

MANDATORY DECISION PROCEDURE:

For every user request:

STEP 1 - INTENT
Identify what the user wants. Use conversation history
when the request refers to an earlier message.

STEP 2 - CAPABILITY CHECK
Before offering to perform an action, inspect the
available tools list.

Find a tool capable of executing the requested action.

If no matching tool exists, the action is UNAVAILABLE.
Do not promise to perform it.

STEP 3 - EXECUTION VERIFICATION
An action is COMPLETED only when a matching successful
tool execution result exists.

Conversation history, previous assistant messages,
and user confirmations are NOT execution evidence.

STEP 4 - RESPONSE
For action requests, first report your capability check
using this format:

Capability: AVAILABLE or UNAVAILABLE
Response: Your answer to the user

If a tool is unavailable, explain that you understand
the request but cannot execute it.

If a tool is available, execution must still be verified
before reporting completion.

Never invent tools, device readings, or execution results.
"""
)


# Store conversation history
history = []

MAX_TURNS = 5


def ask_homemind(user_input):
    global history

    # Add the new user message
    history.append(HumanMessage(content=user_input))

    # Send system instructions + conversation history
    messages = [system_prompt] + history

    response = llm.invoke(messages)

    # Save the assistant response
    history.append(AIMessage(content=response.content))

    # Keep only the most recent 5 exchanges
    history = history[-2 * MAX_TURNS:]

    return response.content


if __name__ == "__main__":

    while True:
        command = input("\nSmart-home command (q to quit): ")

        if command.lower().strip() == "q":
            break

        answer = ask_homemind(command)
        print(f"\nHomeMind: {answer}")