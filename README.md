# HomeMind

HomeMind is an experimental, locally hosted **agentic smart-home assistant** that uses Qwen3-1.7B to interpret natural-language requests, select tools, and control **simulated** devices. Development is documented through manual experiments and upcoming reproducible evaluation.

## Technology and architecture

- **Model:** Qwen3-1.7B via Ollama (`temperature=0`, `reasoning=False`, `num_predict=200`).
- **Tool-calling runtime:** LangChain `create_agent()` and `StructuredTool` wrappers around Python functions.
- **Simulated environment:** `data/home_state.json` persists thermostat **target temperatures**, lights and a front-door lock.
- **Available functions:** `get_home_state`, `set_temperature`, `set_light`, `set_door_lock`.
- **Conversation context:** last five user turns (including tool messages) in RAM; disk persistence is next.

## Progress

| Stage / milestone | Status |
| --- | --- |
| **01 · Prompt engineering and context** | Exploratory experiments complete |
| **02 · Tool schemas, actual execution, persistent house state** | **Implemented; manual tests promising** |
| **02 · Persistent conversation history** | Next |
| **02 · 100-scenario benchmark and GPT-6 judging** | Planned before Stage 03 |
| **03 · Advanced LangGraph workflows, approvals and retries** | Planned |
| **04 · Fine-tuning and controlled baseline comparison** | Planned |

### What has been demonstrated

**Stage 01:** The prompt-only assistant sometimes fabricated device execution. A capability-first decision procedure correctly refused **3/3 action-related queries in one manual session**; this was not a reliability estimate.

**Stage 02:** Python tools now execute through LangChain and update `home_state.json`. Manual runs confirmed a bedroom light action and invalid-device failure; with the current one-shot prompt, `get_home_state` and `set_temperature` generated real tool calls, including a successful living-room change to **20°C**. General questions and a contextual follow-up also worked in that run. Earlier prompt configurations sometimes refused legitimate queries or printed tool names instead of calling them; a broad benchmark is still required.

**Not yet implemented:** persistent dialogue across restarts, systematic 100-case evaluation, and advanced custom workflows. Stage 02 uses `create_agent()` (which is already LangGraph-backed); Stage 03 will focus on explicit orchestration beyond this basic tool loop.

## Files and reports

- [`src/01_baseline_qwen.py`](src/01_baseline_qwen.py) — Stage 01 baseline
- [`src/02_tool_agent_qwen.py`](src/02_tool_agent_qwen.py) — current Stage 02 agent
- [`src/home_tools.py`](src/home_tools.py) — simulated device tools
- [Stage 01 experiments](experiments/stage_01_prompt_engineering.md)
- [Stage 02 implementation checkpoint](experiments/stage_02_tool_calling.md)
- [Project progress webpage](https://engrhamzaaliimran.github.io/homemind.html)
