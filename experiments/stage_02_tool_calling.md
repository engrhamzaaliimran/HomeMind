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

## Experiment rationale — why add a one-shot tool-call example?

**Problem discovered in early Stage 02 testing:** The same Qwen3-1.7B tool-enabled agent sometimes generated authentic structured calls (`set_light` worked), but the behavior was inconsistent across sessions:

1. It occasionally echoed the system prompt's placeholder — “Response: Your answer based on verified results” — without carrying out an action.
2. It sometimes **refused a legitimate `get_home_state` query** and even general questions such as “tell me about Pakistan,” interpreting capability restrictions too broadly.
3. For temperature questions it sometimes answered with only **`get_home_state`** as plain text; for “change it to 21” it printed `set_temperature` plus JSON arguments **without a `TOOL REQUEST` or `TOOL RESULT`**, so no device update was verified.
4. It occasionally conflated a thermostat **target** with measured room temperature.

**Hypothesis and intervention:** We kept the local model, tool registration, agent architecture and generation settings fixed while revising the system prompt. We clarified that general questions do not need tools, home-state queries should use `get_home_state`, and action completion must rely on tool results. We also added **one concrete JSON-format example** showing a bedroom-light request mapped to `set_light` with the correct arguments. Crucially, the prompt states that the example is an *illustration* and the model must make an **actual structured tool call, not print JSON**. This was motivated by the observed distinction between function-call-looking text and genuine LangChain tool calls.

**Subsequent manual observation:** A fresh conversation with the revised one-shot prompt issued a real `get_home_state({})` call and a real `set_temperature(room="living_room", temperature_c=20)` call returning `success: true`. It also answered a Pakistan question normally, recalled the recent living-room setpoint change, and declined an unsupported shower request. On “I am leaving,” however, it **read home state rather than clarify a departure routine**; that behavior remains an issue.

**Experimental caution:** This was **not** a controlled ablation of one-shot prompting. The prompt also changed in other ways, the test conversations differed, and the sample is small. Therefore the data supports “promising follow-up behavior after the revised one-shot prompt,” **not** an isolated causal gain or a validated tool-calling accuracy rate. A planned 100-scenario benchmark will quantify failure rates on a frozen configuration.

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
