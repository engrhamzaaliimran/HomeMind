# HomeMind

HomeMind is an experimental, locally hosted **agentic smart-home assistant** that uses Qwen3-1.7B to interpret natural-language requests, select tools, and control **simulated** devices. Development is documented through manual experiments and a reproducible 100-scenario Stage 02 baseline evaluation.

## Technology and architecture

- **Model:** Qwen3-1.7B via Ollama (`temperature=0`, `reasoning=False`, `num_predict=200`).
- **Tool-calling runtime:** LangChain `create_agent()` and `StructuredTool` wrappers around Python functions.
- **Simulated environment:** `data/home_state.json` persists thermostat **target temperatures**, lights and a front-door lock.
- **Available functions:** `get_home_state`, `set_temperature`, `set_light`, `set_door_lock`.
- **Conversation context (partial):** last five user turns (including tool messages) in RAM. **Pending:** persistent history across restarts, context-window selection/management, and memory-recall validation.

## Progress

| Stage / milestone | Status |
| --- | --- |
| **01 · Prompt engineering and context** | Exploratory experiments complete |
| **02 · Tool schemas, actual execution, persistent house state** | Implemented; baseline evaluation identifies reliability limitations |
| **02 · Reliability fixes from baseline** | **Next priority:** resolve identified failures and re-evaluate before adding memory features |
| **02 · Conversation memory and context management** | **Deferred until reliability fixes are evaluated:** persistence across restarts, safe context selection and follow-up validation |
| **02 · 100-scenario benchmark and GPT-6 judging** | **Completed baseline (18 Oct 2026); 52 full pass / 12 partial / 36 fail** |
| **03 · Advanced LangGraph workflows, approvals and retries** | Planned |
| **04 · Fine-tuning and controlled baseline comparison** | Planned |

### What has been demonstrated

**Stage 01:** The prompt-only assistant sometimes fabricated device execution. A capability-first decision procedure correctly refused **3/3 action-related queries in one manual session**; this was not a reliability estimate.

**Stage 02:** Python tools now execute through LangChain and update `home_state.json`. Manual runs confirmed a bedroom light action and invalid-device failure; with the current one-shot prompt, `get_home_state` and `set_temperature` generated real tool calls, including a successful living-room change to **20°C**. General questions and a contextual follow-up also worked in that run. Earlier prompt configurations sometimes refused legitimate queries or printed tool names instead of calling them. The subsequent controlled, frozen-configuration 100-scenario baseline shows actual tool execution, but significant identifier and response-honesty errors (see evaluation below).

### Why we introduced one-shot tool prompting

The first Stage 02 prompts produced **inconsistent tool calling**: Qwen sometimes invoked tools correctly, but in other runs rejected supported home-state queries and ordinary general-knowledge questions. It also sometimes returned just `get_home_state` or printed a `set_temperature` JSON object **as answer text**, with no actual LangChain tool execution. The earlier response-format placeholder was occasionally copied verbatim.

**Hypothesis:** a concrete one-shot example mapping “Turn on the bedroom light” to `set_light(room="bedroom", on=True)`, together with an instruction to use the **structured tool-call interface rather than print JSON**, could improve tool selection and execution on the small Qwen3-1.7B model.

**Observed after the change:** one manual session showed actual `get_home_state` and `set_temperature` calls with tool results, a normal general-knowledge answer, correct follow-up recall, and an unsupported-action refusal. This is **suggestive, not proof**: the sessions were not paired or repeated enough to attribute the improvement to one-shot prompting or estimate reliability. [Detailed experimental rationale and observations](experiments/stage_02_tool_calling.md).

**Next priority:** systematically address the limitations identified in the 100-scenario baseline and re-run the benchmark before implementing storage or long-term conversational memory. **Not yet complete:** persistent dialogue across restarts, context management/recall, and advanced custom workflows. Stage 02 uses `create_agent()` (which is already LangGraph-backed); Stage 03 will focus on explicit orchestration beyond this basic tool loop.

## Stage 02 baseline evaluation — 18 October 2026

The **100-scenario benchmark** exercised the current **one-shot Stage 02 system prompt** and registered LangChain tools; it extracts agent configuration directly from `src/02_tool_agent_qwen.py` (before the interactive input loop). It uses isolated simulated home state, starts each scenario with empty conversation history, preserves the same last-five-turn RAM context behavior and records structured tool calls, results, messages and state transitions. Ten scenarios included setup turns: **120 model requests** total.

**Results:** 100/100 scenarios completed without top-level runtime errors. GPT-6 **qualitative review** assigned **52 pass / 12 partial / 36 fail** (58/100 with half credit for partial). The runner's deterministic checks verified **14/35 (40%)** expected write sequences, while **96/100** cases had no unrequested state mutation. These numbers measure different outcomes and must not be conflated.

Most prominent problems: noncanonical device IDs (e.g. `living room` instead of `living_room`); incorrect tool actions for unsupported requests; unsupported completion claims; missed clarifications; and treating target thermostat setpoints as measured temperatures. Some conversation-context scenarios had earlier setup actions fail; these should not be counted as isolated memory failures.

## Immediate development priority — reliability before memory

**The first target is to fix each limitation identified in the Stage 02 evaluation before moving to persistent storage or conversation-context/memory features.** The present five-turn RAM context remains unchanged while these fixes are tested. We will use the frozen 100-scenario benchmark to compare improvements against the baseline, recording any remaining failures rather than assuming they are resolved.

1. **Tool arguments and device IDs:** normalize or validate room and door identifiers; reject invalid targets clearly.
2. **Capability boundaries:** prevent unsupported operations from triggering a superficially related but unauthorized tool action.
3. **Ambiguity handling:** request clarification when a room, device, target value or intended action is unspecified.
4. **Execution honesty:** verify actual tool results before claiming completion; report partial success and failures accurately.
5. **State-reading faithfulness:** distinguish configured thermostat setpoints from measured temperature; avoid ungrounded state claims.
6. **Multi-tool and conversation consistency:** handle partial multi-action outcomes, follow-up references and setup failures reliably, while detecting unexpected state mutations.

**Exit criterion:** re-run all 100 scenarios with the same evaluation criteria; inspect previously failing cases and regressions, and document unresolved limitations. Only **after this reliability phase** should HomeMind proceed to persistent conversation storage, retrieval, summarization, and broader context/memory experiments. Existing device-state JSON persistence is separate from (and does not implement) conversational memory.

**Methodological constraints:** one non-random challenge set, one local run, simulated devices; actual Ollama context allocation not recorded. The GPT-6 judgments are qualitative and should not be treated as an independent model-based scoring script or an unbiased reliability estimate. No changes to the Stage 02 agent/prompt were introduced for this baseline.

**Reproduce (with Ollama and dependencies running locally):**

```bash
python src/03_run_evaluation.py --limit 5
python src/03_run_evaluation.py
```

The runner writes timestamped JSONL to `experiments/results/`. Check the raw and judged traces together; the judged file contains reviewer verdicts, not model responses produced by the local agent.

**Baseline outputs:** [Full evaluation report](experiments/stage_02_evaluation_report.md) · [100-question bank](experiments/stage_02_100_questions.md) · [Benchmark fixtures](experiments/stage_02_benchmark_100.jsonl) · [Raw local run](experiments/results/stage_02_eval_20261018_152127.jsonl) · [Judged 100-case output](experiments/results/stage_02_judged_20261018_152127.jsonl).

## Files and reports

- [`src/01_baseline_qwen.py`](src/01_baseline_qwen.py) — Stage 01 baseline
- [`src/02_tool_agent_qwen.py`](src/02_tool_agent_qwen.py) — current Stage 02 agent
- [`src/home_tools.py`](src/home_tools.py) — simulated device tools
- [`src/03_run_evaluation.py`](src/03_run_evaluation.py) — Stage 02 reproducible evaluation runner
- [Stage 01 experiments](experiments/stage_01_prompt_engineering.md)
- [Stage 02 implementation checkpoint](experiments/stage_02_tool_calling.md)
- [Project progress webpage](https://engrhamzaaliimran.github.io/homemind.html)
