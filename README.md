# HomeMind

HomeMind is a work-in-progress **agentic smart-home assistant** built around a compact, locally hosted language model. The goal is to translate everyday language into **verifiable simulated device actions** while tracking progress through documented experiments.

## Technology

- **Baseline LLM:** Qwen3-1.7B with Ollama and LangChain
- **Stateful orchestration (planned):** LangGraph
- **Tool execution (planned):** Python functions controlling simulated lights, heating and locks
- **Model adaptation (planned):** LoRA; evaluate against the untuned baseline

## Progress

| Stage | Scope | Status |
| --- | --- | --- |
| **01** | Baseline inference, conversational history and prompt engineering | **Exploratory experiments recorded** |
| **02** | Structured tool calling, simulated device state, execution verification | Planned |
| **03** | LangGraph agentic workflows, confirmations and failure recovery | Planned |
| **04** | Evaluation dataset, LoRA and comparative model evaluation | Planned |

### Stage 01 — Key result

Initial prompting correctly interpreted thermostat requests and recalled temperature corrections, but sometimes **falsely reported that device actions were completed**, despite having no tools. General behavioral rules and an explicit empty capability list did not reliably prevent this. A mandatory **intent → capability check → execution evidence → response** procedure produced **3 correct capability/action responses out of 3 observed** in one exploratory session.

This is not a reliability benchmark. A future tool-enabled implementation must enforce availability and execution status in Python rather than relying on generated text.

- [Full Stage 01 experimental log](experiments/stage_01_prompt_engineering.md)
- [Project progress webpage](https://engrhamzaaliimran.github.io/homemind.html)
- [Current baseline source](src/01_baseline_qwen.py)

**Current limitations:** No implemented smart-home execution tools, no LangGraph orchestration, and no LoRA training results yet.
