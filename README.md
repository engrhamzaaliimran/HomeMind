# HomeMind

HomeMind is an experimental, locally hosted **agentic smart-home assistant** that uses Qwen3-1.7B to interpret natural-language requests, select tools, and control **simulated** devices. Development is documented through manual experiments, a reproducible 100-scenario Stage 02 baseline, a Stage 02.1 Python normalization experiment, Stage 02.2 execution-honesty prompting, and Stage 02.3 independent Qwen3-0.6B claim verification.

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
| **02.1 · Python device-ID normalization and serialized JSON access** | **Implemented and evaluated:** 100/100 scenarios completed; **33/35** verified actions; **73 pass / 7 partial / 20 fail** qualitative judgments |
| **02.2 · Execution-honesty prompt safeguards** | **Implemented and evaluated:** 33/35 verified action sequences; 99/100 cases without unauthorized changes (vs 96/100 in Stage 02.1). Remaining fabricated success claims. |
| **02.2 variant · Explicit tool descriptions** | **Evaluated separately:** 33/35 verified actions; 98/100 cases without unauthorized changes. No further overall improvement. |
| **02.3 · Qwen3-0.6B structured claim verifier** | **Evaluated:** 100/100 scenarios; 75 pass / 15 partial / 10 fail in qualitative review; detects targeted fabricated success claims but still has false rejections. |
| **02 · Remaining reliability fixes** | **Next priority:** capability validation, clarification, execution honesty and multi-action handling before memory features |
| **02 · Conversation memory and context management** | **Deferred until reliability fixes are evaluated:** persistence across restarts, safe context selection and follow-up validation |
| **02 · 100-scenario baseline and evaluation** | Completed: **52 pass / 12 partial / 36 fail**; retained unchanged for comparison |
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

## Stage 02.3 — Qwen3-0.6B execution-claim verification (20 October 2026)

**Status:** Experimental, evaluated; validator prompt refinement planned. Stage 02.2 remains the baseline. This experiment does **not** alter the Stage 02.2 prompt or device tools.

**Objective:** Prevent the assistant from falsely asserting that smart-home operations succeeded while preserving natural-language replies.

**Pipeline:**
1. **Qwen3-1.7B main agent** interprets the request, invokes real LangChain tools, and drafts the answer.
2. An independent **Qwen3-0.6B extractor** converts *asserted* action, past-action and device-state claims into structured JSON.
3. **Python verification** compares the claims with genuine successful tool results and state reads (including bounded prior-turn evidence for past actions).
4. An unsupported claim triggers **one tool-free Qwen3-1.7B revision**, followed by re-extraction and verification; a second failure results in a conservative fallback.

**Files:**
- [Claim-verifier agent](src/02_3_claim_verifier_agent.py)
- [100-scenario evaluation runner](src/03_run_claim_evaluation.py) — wraps the existing `src/03_run_evaluation.py` protocol.
- [Full JSONL results — 20 October 2026](experiments/results/stage_02_eval_20261020_225733.jsonl) — raw user turns, final outputs, tool traces, state changes, extracted claims, verdicts and correction decisions.

**Reproduce** (from repository root; Ollama must be running with `qwen3:1.7b` and `qwen3:0.6b` pulled):

```bash
ollama pull qwen3:0.6b
python src/03_run_claim_evaluation.py --ids HM092 HM093 HM094
python src/03_run_claim_evaluation.py
```

The evaluation uses the **same 100 benchmark scenarios / 120 user turns**, isolated starting states, real tool executions and deterministic checks as earlier Stage 02 experiments. The new runner adds `claim_verification` diagnostics to each turn.

| Measure | Stage 02.3 result |
| --- | ---: |
| Scenarios completed | 100 / 100 |
| Expected write sequences verified after device-ID normalization | 33 / 35 (94.3%) |
| Scenarios with no unauthorized state change | 98 / 100 |
| Real tool calls | 81 |
| Accepted responses without revision | 87 / 120 |
| Responses skipped by keyword filter | 22 / 120 |
| Responses flagged for revision | 11 / 120 |
| Revisions accepted after second check | 5 |
| Safe fallbacks after failed second check | 6 |

**Qualitative review:** Stage 02.3 yielded **75 pass / 15 partial / 10 fail**, for **82.5/100** with partial counted as half credit. The earlier Stage 02.2 review yielded **73 pass / 16 partial / 11 fail** (81/100). These are human qualitative classifications, **not machine-generated labels stored in the raw JSONL**, and the small difference should not be treated as a statistically established improvement.

**Key result:** The extractor/verifier identified and blocked or corrected fabricated execution assertions in **HM092, HM093 and HM094** (door locked, bedroom lamp turned on, and living-room setpoint changed despite no successful tool execution). It also incorrectly rejected valid results for **HM009, HM040 and HM084** because it confused *locked* with *unlocked*, and mishandled previous-turn evidence in **HM085**. **HM034** retained a false claim about a nonexistent kitchen thermostat. Two scenarios (**HM059 and HM060**) produced unauthorized tool effects; checking the wording of the final response cannot undo those effects. Some relevant answers escaped checking because the current system uses a keyword gate.

**Next iteration:** Refine the extractor prompt for negation, temporal language and unknown devices; ensure complete verification coverage; benchmark unsupported claims caught *and* legitimate claims wrongly rejected using the same frozen scenarios before considering deployment.

---

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

**Remaining failures and risks:** HM042 generated `room="all"` instead of enumerating lights, so only the door-lock action succeeded; HM090 failed to execute the requested follow-up temperature increase. Four cases still changed device state without adequate authorization (HM059, HM060, HM063, HM069). Python ID normalization cannot fix unsupported-capability claims, ambiguity, incorrect intent, or unsupported execution claims. **Stage 02.1 response-level qualitative review:** 73 pass / 7 partial / 20 fail, compared with the Stage 02 baseline's 52 / 12 / 36. The reviewer examined the newer tool results, device-state changes, and final answers (including normalization evidence). These are qualitative judgments from one run of a challenge set, **not** an independent production reliability estimate. [Browse all 100 updated Stage 02.1 questions, responses and verdicts on the project website](https://engrhamzaaliimran.github.io/homemind.html#question-browser). The repository retains the raw Stage 02.1 trace; an independently exported, separate Stage 02.1 judged JSONL has not been committed.

### Updated qualitative results (100 scenarios)

| Outcome | Stage 02 baseline | Stage 02.1 |
| --- | ---: | ---: |
| Full pass | 52 | **73** |
| Partial pass | 12 | **7** |
| Fail | 36 | **20** |

| Category | Stage 02 full passes | Stage 02.1 full passes |
| --- | ---: | ---: |
| Single-device control | 9/20 | **20/20** |
| Home-state questions | 11/15 | **11/15** |
| Multi-device commands | 2/10 | **9/10** |
| Unsupported / invalid requests | 11/15 | **13/15** |
| Ambiguity / clarification | 1/10 | **1/10** |
| General knowledge | 9/10 | **9/10** |
| Conversation context | 6/10 | **7/10** |
| Execution honesty | 3/10 | **3/10** |

**What improved:** deterministic device-ID normalization repaired common mismatches such as `living room` → `living_room`. A process-local lock prevented concurrent accesses from corrupting simulated state JSON. Verified action sequences improved **14/35 → 33/35** on the same benchmark, without changing the Stage 02 system prompt or Qwen settings. **What remains:** capability enforcement, ambiguous instructions, unsupported success claims and some multi-action/context handling.

### Stage 02.1 agent execution pipeline

This is the **same Mermaid flowchart displayed on the [HomeMind project page](https://engrhamzaaliimran.github.io/homemind.html#execution-pipeline)**. Click to expand.

<details>
<summary>View execution pipeline flowchart</summary>

```mermaid
flowchart TD
    A([START]) --> B[/User enters a command/]
    B --> C["Load recent conversation context<br/>Last 5 turns in RAM"]
    C --> D["Qwen3-1.7B<br/>Intent understanding + tool selection"]

    D --> E{"What type of request?"}

    E -->|General knowledge| F[/Generate normal answer/]
    E -->|Home-state query| G["get_home_state()"]
    E -->|Device action| H{"Did Qwen generate<br/>a structured tool call?"}
    E -->|Unsupported or unclear| I[/Qwen should refuse or clarify/]

    H -->|No| J[/Generate response without execution/]
    H -->|Yes| K["Python argument validation"]

    K --> L{"Valid device ID?"}
    L -->|Yes| P["Execute original Python tool"]
    L -->|No| M{"Known alias or<br/>deterministic normalization?"}

    M -->|Yes| N["Convert to canonical ID<br/>e.g. living room → living_room"]
    N --> P
    M -->|No| O["Return INVALID_DEVICE_ID<br/>No action executed"]

    P --> Q["Protected JSON access<br/>threading.RLock"]
    Q --> R[("home_state.json<br/>Simulated device state")]
    R --> S{"Tool returned<br/>success = true?"}

    S -->|Yes| T["Return successful tool result"]
    S -->|No| U["Return failure and error"]

    G --> R
    O --> V["Qwen receives tool result"]
    T --> V
    U --> V

    V --> W[/Qwen generates final response/]
    F --> X["Update recent conversation<br/>history in RAM"]
    I --> X
    J --> X
    W --> X

    X --> Y([END])

    classDef start fill:#def3e9,stroke:#26846a,color:#155443
    classDef process fill:#e6eeff,stroke:#4d78c0,color:#193d79
    classDef decision fill:#fff0ce,stroke:#c28c2b,color:#674514
    classDef datastore fill:#eee6fc,stroke:#9165c0,color:#4f3178
    classDef output fill:#e8f5f4,stroke:#339b8e,color:#19554f

    class A,Y start
    class C,D,G,K,N,P,Q,T,U,V,X process
    class E,H,L,M,S decision
    class R datastore
    class B,F,I,J,O,W output
```

</details>

**Symbols:** oval = start/end; parallelogram = input/output; rectangle = operation; diamond = decision; cylinder = simulated device-state JSON. **Current limitation:** the capability and ambiguity decision is still instructed by the model prompt, not enforced by an independent Python policy. JSON locking is in-process only. The flowchart illustrates intended high-level paths; unsupported claims remain an observed failure mode.

**Run Stage 02.1 interactively:**

```bash
python src/02_tool_agent_qwen_with_normalization_check.py
```

**Reproduce the same benchmark:** in `src/03_run_evaluation.py`, set `AGENT_FILE = ROOT / "src" / "02_tool_agent_qwen_with_normalization_check.py"` (instead of the baseline filename); then run `python src/03_run_evaluation.py` from the repository root. The benchmark uses a temporary simulated state and records results in `experiments/results/`. Keep the original benchmark fixtures unchanged.

**Evidence:** [Stage 02.1 raw 100-scenario trace](experiments/results/stage_02_01_eval_20261018_181720.jsonl) · [Stage 02 baseline trace](experiments/results/stage_02_eval_20261018_152127.jsonl) · [Benchmark scenarios](experiments/stage_02_benchmark_100.jsonl).

## Stage 02.2 — Prompt safeguards and explicit tool descriptions (18 October 2026)

**Question:** Can more explicit execution-honesty instructions help the local Qwen3-1.7B agent reject unsupported user assertions, avoid fabricated success claims, and refrain from unauthorized actions? The same 100-case fixed challenge set and Stage 02.1 Python ID normalization/JSON locking were retained. Only one local run per configuration is available.

**Prompt-only variant** ([agent source](src/02_2_tool_agent_qwen_execution_honesty.py)): adds four high-priority instructions to the Stage 02.1 system prompt: (1) verify current state and past actions using actual tool evidence rather than user assertions; (2) refuse unsupported, unauthorized, unsafe, or illegal operations; (3) never pretend an action succeeded without a real successful tool result; and (4) refuse contradictory simultaneous write requests. Tool names, signatures, underlying Python behavior, model settings, and RAM history remain the same.

**Explicit-description variant** ([agent source](src/02_2_tool_agent_qwen_explicit_descriptions.py)): keeps the new prompt and additionally provides four positive-only capability descriptions directly through `StructuredTool.from_function(description=...)`. Simply expanding underlying `home_tools.py` docstrings would not change the descriptions of the checked wrappers registered with LangChain.

### Deterministic before/after checks

| Same 100-scenario benchmark | Stage 02.1 | Stage 02.2: prompt only | Stage 02.2: prompt + descriptions |
| --- | ---: | ---: | ---: |
| Completed scenarios | 100/100 | 100/100 | 100/100 |
| Independently verified expected write/action sequences | 33/35 | 33/35 | 33/35 |
| Scenarios without unrequested state mutations | 96/100 | **99/100** | 98/100 |
| Scenarios with unrequested state mutations | 4 (HM059, HM060, HM063, HM069) | **1 (HM059)** | 2 (HM059, HM060) |

These are **different deterministic measures**, not an overall success rate. A subsequent GPT-6 qualitative review of all 100 Stage 02.2 prompt-only traces assigned **73 full passes / 16 partial passes / 11 failures**, compared with **73 / 7 / 20** for Stage 02.1. The full-pass count stayed unchanged, while nine previous failures were reduced to partial outcomes on net. This is a one-pass subjective review, not independently validated reliability.

**Observed behaviors:** The Stage 02.2 prompt-only run improved the response to HM091 (claim about an unverified earlier light action) and HM098 (demand to state unverified door status). However, HM092–HM094 still produced false completion claims without real tool execution; HM095 did not successfully invoke the state-reading tool; and HM100 remained vulnerable to a fabricated blinds-action claim. Adding tool descriptions did not fix these failures. In HM060 the description variant even turned on a light when the user requested opening blinds, producing one additional unauthorized state change relative to prompt-only.

**Interpretation:** These results support a *limited reduction in unauthorized state changes* associated with the added prompt rules, not a verified resolution of execution honesty or robust policy enforcement. Prompt wording and tool descriptions are model-facing guidance, **not deterministic Python authorization checks**. The stronger observed safety result is the prompt-only variant; further work should test intent-to-capability validation and evidence-grounded response verification. Single runs with temperature 0 do not establish statistical significance or out-of-sample generalization.

**Reproduce:** Set `AGENT_FILE` in `src/03_run_evaluation.py` to `ROOT / "src" / "02_2_tool_agent_qwen_execution_honesty.py"` (or `02_2_tool_agent_qwen_explicit_descriptions.py`) and run `python src/03_run_evaluation.py`. The archived traces retain the recorded agent-source and prompt SHA-256 fingerprints. The committed scripts reproduce the intended configurations, but documentation/comment changes mean their file bytes are not identical to the archived run snapshots.

**Raw traces:** [Stage 02.1](experiments/results/stage_02_01_eval_20261018_181720.jsonl) · [Stage 02.2 prompt only](experiments/results/stage_02_eval_20261018_204026.jsonl) · [Stage 02.2 prompt + descriptions](experiments/results/stage_02_eval_20261018_211624.jsonl).

**Qualitative reviews (100 records each):** [Stage 02.1 archived judgments](experiments/results/stage_02_01_qualitative_review_20261018.jsonl) · [Stage 02.2 prompt-only judgments](experiments/results/stage_02_02_prompt_qualitative_review_20261020.jsonl). Both apply the same pass/partial/fail rubric; judgments can be subjective, especially the partial category.

## Immediate development priority — reliability before memory

**The first target is to fix each limitation identified in the Stage 02 evaluation before moving to persistent storage or conversation-context/memory features.** The present five-turn RAM context remains unchanged while these fixes are tested. We will use the frozen 100-scenario benchmark to compare improvements against the baseline, recording any remaining failures rather than assuming they are resolved.

1. **Tool arguments and device IDs:** **Stage 02.1 implemented and verified** deterministic normalization. Continue monitoring rejected/ambiguous identifiers and unexpected side effects.
2. **Capability boundaries:** prevent unsupported operations from triggering a superficially related but unauthorized tool action.
3. **Ambiguity handling:** request clarification when a room, device, target value or intended action is unspecified.
4. **Execution honesty:** verify actual tool results before claiming completion; report partial success and failures accurately.
5. **State-reading faithfulness:** distinguish configured thermostat setpoints from measured temperature; avoid ungrounded state claims.
6. **Multi-tool and conversation consistency:** handle partial multi-action outcomes, follow-up references and setup failures reliably, while detecting unexpected state mutations.

**Exit criterion:** re-run all 100 scenarios with the same evaluation criteria; inspect previously failing cases and regressions, and document unresolved limitations. Only **after this reliability phase** should HomeMind proceed to persistent conversation storage, retrieval, summarization, and broader context/memory experiments. Existing device-state JSON persistence is separate from (and does not implement) conversational memory.

**Methodological constraints:** one non-random challenge set and one completed local run per version, using simulated devices; actual Ollama context allocation was not recorded. GPT-6 verdicts are qualitative, not an independently validated reliability estimate. Python normalization improves execution but does not guarantee policy compliance. Original Stage 02 agent/prompt are frozen as a comparison baseline.

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
- [`src/02_2_tool_agent_qwen_execution_honesty.py`](src/02_2_tool_agent_qwen_execution_honesty.py) — Stage 02.2 prompt-only execution-honesty safeguards
- [`src/02_2_tool_agent_qwen_explicit_descriptions.py`](src/02_2_tool_agent_qwen_explicit_descriptions.py) — Stage 02.2 prompt plus explicit registered tool descriptions
- [`src/home_tools.py`](src/home_tools.py) — simulated device tools
- [`src/03_run_evaluation.py`](src/03_run_evaluation.py) — Stage 02 reproducible evaluation runner
- [Stage 01 experiments](experiments/stage_01_prompt_engineering.md)
- [Stage 02 implementation checkpoint](experiments/stage_02_tool_calling.md)
- [Project webpage and interactive Stage 02.1 evaluation](https://engrhamzaaliimran.github.io/homemind.html)
- [Expandable execution flowchart on website](https://engrhamzaaliimran.github.io/homemind.html#execution-pipeline)
