# Stage 02 — Structured tool calling (implementation checkpoint)

**Recorded:** 11 October 2026  
**Reference implementation:** [`da16b878`](https://github.com/engrhamzaaliimran/HomeMind/commit/da16b878370caee1831f933622baf16831bdcced)  
**Status:** Tool-enabled prototype working in manual tests; **conversation memory/context management** and systematic evaluation pending.

## Implementation

- **Model:** local Qwen3-1.7B via Ollama/LangChain; `temperature=0`, `reasoning=False`, `num_predict=200` (held from Stage 01).
- **Agent:** `src/02_tool_agent_qwen.py` using LangChain `create_agent()`, `StructuredTool.from_function()`, structured tool calls and result messages.
- **Tools:** `get_home_state`, `set_temperature`, `set_light`, `set_door_lock` in `src/home_tools.py`.
- **State:** persistent `data/home_state.json`, containing bedroom/living-room thermostat **setpoints**, lights and front-door lock.
- **Conversation:** recent five complete user turns held **in memory only**; not yet persisted across restarts. Context-window selection, safe turn retention and follow-up recall need additional testing.
- **Prompt:** carries Stage 01 intent → capability → verification → response logic, distinguishes general questions from device tasks, and adds a **one-shot JSON illustration** of structured tool selection.

## Manual observations

| Test / prompt version | Observed behavior | Finding |
| --- | --- | --- |
| Earlier Stage 02 prompt: bedroom light on | `set_light(room="bedroom", on=True)` → `success: true` | Tool selection and execution worked |
| Earlier prompt: turn on shower | `set_light(room="shower", on=True)` → `success: false` | Invalid device correctly rejected by Python |
| Earlier prompt: ask home status/temperature | Sometimes refused even with `get_home_state`; sometimes printed a tool name or JSON instead of calling it | Tool-selection/response failures remained |
| Current **one-shot** prompt: “I am leaving can you get the home ready?” | `get_home_state({})` executed, state accurately listed | Read-state tool worked; departure routine not planned or clarified |
| Current prompt: living-room thermostat to 20°C | `set_temperature(room="living_room", temperature_c=20)` → `success: true`; response confirmed 20°C target | Verified state-changing action |
| Current prompt: “tell me about Pakistan” | Answered normally without a tool | General knowledge routing worked |
| Current prompt: “what was the temperature you recently changed” | Recalled living-room setpoint 20°C | Multi-turn recall observed |
| Current prompt: shower for plants | Declined unsupported action without claiming execution | Correct limitation reporting |

**Interpretation:** The revised one-shot prompt is *promising* compared with earlier manually tested prompts, but these are small, non-paired conversations; no accuracy percentage or causal improvement estimate is justified. No exhaustive multi-device or regression testing has been run. No claim of eliminating hallucinations is warranted.

## Next steps before Stage 03

1. Add and validate persistent conversation memory **and context management**: preserve `AIMessage.tool_calls` and matching `ToolMessage` IDs without replaying past actions; select recent relevant context and test follow-up recall across restarts.
2. Build **100 isolated test scenarios** with initial state, expected tool calls, expected final state and captured responses.
3. Save run evidence to JSONL. Use deterministic checks for tools/state, plus **GPT-6 review** for response quality and unsupported claims. Produce a small Stage 02 evaluation report.

Keep the model and current one-shot prompt **unchanged** during the baseline evaluation.

**Scope note:** Stage 03 adds *custom* LangGraph workflows, retries and confirmation policies; `create_agent()` in Stage 02 already uses a LangGraph-backed agent runtime.
