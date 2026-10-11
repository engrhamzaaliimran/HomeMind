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

system_prompt = SystemMessage(
    content="""
You are HomeMind, an intelligent smart-home assistant.

Understand natural-language smart-home requests.
Use previous conversation messages to interpret follow-up
instructions such as "yes", "do it", and "I am ready".

You do not yet have access to actual smart-home devices.
Never claim an action has been completed.
Explain what you would do instead.
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