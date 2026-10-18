# HomeMind

HomeMind is an experimental, locally hosted **agentic smart-home assistant** that uses Qwen3-1.7B to interpret natural-language requests, select tools, and control **simulated** devices. Development is documented through manual experiments, a reproducible 100-scenario Stage 02 baseline, and a Stage 02.1 Python normalization experiment.

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
| **02.1 · Python device-ID normalization and serialized JSON access** | **Implemented and benchmarked:** 100/100 scenarios ran; 33/35 expected action sequences verified after normalization (vs. 14/35 baseline) |
| **02 · Remaining reliability fixes** | **Next priority:** capability validation, clarification, execution honesty and multi-action handling before memory features |
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

**Next priority:** systematically address the remaining limitations identified in Stage 02 and 02.1 evaluations, and re-run the benchmark before implementing storage or long-term conversational memory. **Not yet complete:** persistent dialogue across restarts, context management/recall, and advanced custom workflows. Stage 02 uses `create_agent()` (which is already LangGraph-backed); Stage 03 will focus on explicit orchestration beyond this basic tool loop.

## Stage 02 baseline evaluation — 18 October 2026

The **100-scenario benchmark** exercised the current **one-shot Stage 02 system prompt** and registered LangChain tools; it extracts agent configuration directly from `src/02_tool_agent_qwen.py` (before the interactive input loop). It uses isolated simulated home state, starts each scenario with empty conversation history, preserves the same last-five-turn RAM context behavior and records structured tool calls, results, messages and state transitions. Ten scenarios included setup turns: **120 model requests** total.

**Results:** 100/100 scenarios completed without top-level runtime errors. GPT-6 **qualitative review** assigned **52 pass / 12 partial / 36 fail** (58/100 with half credit for partial). The runner's deterministic checks verified **14/35 (40%)** expected write sequences, while **96/100** cases had no unrequested state mutation. These numbers measure different outcomes and must not be conflated.

Most prominent problems: noncanonical device IDs (e.g. `living room` instead of `living_room`); incorrect tool actions for unsupported requests; unsupported completion claims; missed clarifications; and treating target thermostat setpoints as measured temperatures. Some conversation-context scenarios had earlier setup actions fail; these should not be counted as isolated memory failures.

## Stage 02.1 — Python argument normalization (18 October 2026)

**Goal:** reduce single-device failures where the LLM chooses the correct tool but generates a noncanonical device identifier such as `living room` instead of `living_room`. This is an application-layer reliability patch, not an LLM fine-tune or prompt change.

**Implementation:** [`src/02_tool_agent_qwen_with_normalization_check.py`](src/02_tool_agent_qwen_with_normalization_check.py) preserves the original Stage 02 agent (`src/02_tool_agent_qwen.py`) as a baseline. It registers three checked wrappers with the **same public tool names, argument signatures and system prompt**. Python normalizes only deterministic separator/case variants and explicitly reviewed aliases, verifies that the resolved device supports the requested property, and then calls the existing write function. Unknown/fuzzy matches are rejected rather than guessed. Tool results include `device_id_normalization: {from, to}` when a correction occurs. An in-process `threading.RLock` serializes state reads and complete read–modify–write operations to prevent JSON corruption when LangChain runs multiple tools concurrently. This lock does **not** coordinate independent Python processes.

**What did not change:** Qwen3-1.7B, model settings, one-shot Stage 02 prompt (same SHA-256 fingerprint), four exposed tool names, five-turn RAM conversation history, and `src/home_tools.py`. The original agent script remains available for replication.

### Before/after benchmark

Both local runs used the same 100 scenarios (120 user requests including setup turns), with fresh state per scenario. Stage 02.1 completed **100/100** cases without runtime errors, including multi-device cases that had triggered overlapping JSON writes in an earlier aborted attempt.

| Deterministic measure | Stage 02 baseline | Stage 02.1 |
| --- | ---: | ---: |
| Expected write/action sequences with verified tool results | 14/35 (40.0%) | **33/35 (94.3%)** |
| Single-device target action sequences | 9/20 | **20/20** |
| Multi-device target action sequences | 2/10 | **9/10** |
| Context-dependent target action sequences | 3/5 | **4/5** |
| Expected final-state fields check | 84/100 | **98/100** |
| No unrequested device-state changes | 96/100 | **96/100** |

**Metric distinction:** the evaluation runner's original `required_calls_pass` and `expected_write_results_pass` check **raw LLM arguments** against exact canonical IDs. They therefore do not fully credit normalization. The 33/35 measure was independently computed from the logged tool-call IDs, original arguments, `device_id_normalization.to` where present, actual `success: true` results, and expected arguments. Across the run, **28 tool results contained normalization records, 27 of which succeeded**; the remaining one was correctly rejected by temperature-range validation (5°C). Final-state-field checks can be vacuously true in cases with no expected fields; they are **not** an overall accuracy measure.

**Remaining failures and risks:** HM042 generated `room="all"` instead of enumerating lights, so only the door-lock action succeeded; HM090 failed to execute the requested follow-up temperature increase. Four cases still changed device state without adequate authorization (HM059, HM060, HM063, HM069). Python ID normalization cannot fix unsupported-capability claims, ambiguity, incorrect intent, or unsupported execution claims. **No new GPT-6 qualitative pass/partial/fail review has yet been performed for Stage 02.1.** The baseline's 52/12/36 judged split must not be reused as Stage 02.1's score.

**Run Stage 02.1 interactively:**

```bash
python src/02_tool_agent_qwen_with_normalization_check.py
```

**Reproduce the same benchmark:** in `src/03_run_evaluation.py`, set `AGENT_FILE = ROOT / "src" / "02_tool_agent_qwen_with_normalization_check.py"` (instead of the baseline filename); then run `python src/03_run_evaluation.py` from the repository root. The benchmark uses a temporary simulated state and records results in `experiments/results/`. Keep the original benchmark fixtures unchanged.

**Evidence:** [Stage 02.1 raw 100-scenario trace](experiments/results/stage_02_01_eval_20261018_181720.jsonl) · [Stage 02 baseline trace](experiments/results/stage_02_eval_20261018_152127.jsonl) · [Benchmark scenarios](experiments/stage_02_benchmark_100.jsonl).

## Immediate development priority — reliability before memory

**The first target is to fix each limitation identified in the Stage 02 evaluation before moving to persistent storage or conversation-context/memory features.** The present five-turn RAM context remains unchanged while these fixes are tested. We will use the frozen 100-scenario benchmark to compare improvements against the baseline, recording any remaining failures rather than assuming they are resolved.

1. **Tool arguments and device IDs:** **Stage 02.1 implemented and verified** deterministic normalization. Continue monitoring rejected/ambiguous identifiers and unexpected side effects.
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
- [`src/02_tool_agent_qwen.py`](src/02_tool_agent_qwen.py) — frozen Stage 02 baseline agent
- [`src/02_tool_agent_qwen_with_normalization_check.py`](src/02_tool_agent_qwen_with_normalization_check.py) — Stage 02.1 normalization and safe in-process state access
- [`src/home_tools.py`](src/home_tools.py) — simulated device tools
- [`src/03_run_evaluation.py`](src/03_run_evaluation.py) — Stage 02 reproducible evaluation runner
- [Stage 01 experiments](experiments/stage_01_prompt_engineering.md)
- [Stage 02 implementation checkpoint](experiments/stage_02_tool_calling.md)
- [Project progress webpage](https://engrhamzaaliimran.github.io/homemind.html)
