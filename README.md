# GharMind

[Previously HomeMind — why the name changed](#naming-history)

**GharMind** (گھر مائنڈ; Urdu *Ghar*, “home”, + English *Mind*) is a local, experimental **agentic smart-home assistant** built with Qwen3, Ollama, LangChain, and Python. It translates natural-language requests into real tool calls that operate on a **simulated** home, then checks whether its responses are supported by execution evidence.

[Project page & interactive evaluations](https://engrhamzaaliimran.github.io/homemind.html) · [Benchmark dataset](experiments/stage_02_benchmark_100.jsonl) · [Latest results](experiments/results/stage_02_eval_20261020_225733.jsonl)

> **Research prototype:** Device control is simulated. Neither prompt safeguards nor response verification currently guarantee correct or authorized actions.

## Naming history

**Previously HomeMind.** This independent research project was previously called *HomeMind*. It was renamed *GharMind* to distinguish it from existing projects. The repository name and website URL remain unchanged to preserve existing links and citations.

## Architecture

```text
User request
    ↓
Qwen3 1.7B agent → LangChain tools → simulated home_state.json
    ↓                    ↓
Natural-language reply   Tool execution evidence
    ↓                    ↓
Qwen3 0.6B claim extractor (Stage 02.3)
    ↓
Python claim-to-evidence verification
    ├─ Supported → return original response
    └─ Unsupported → one tool-free Qwen3 correction → recheck
                                                  └─ fallback if still unsupported
```

- **Main agent:** `qwen3:1.7b` via Ollama; LangChain `create_agent()`.
- **Verifier (experimental):** `qwen3:0.6b` extracts structured action/state claims; Python checks actual tool receipts.
- **Tools:** `get_home_state`, `set_temperature`, `set_light`, `set_door_lock`.
- **State:** `data/home_state.json` stores light/lock status and thermostat **setpoints**, not measured temperatures.
- **Context:** Last five user turns in RAM. Conversation persistence/retrieval is not yet implemented.

**Important:** The verifier checks *responses after tool execution*. It cannot prevent an unauthorized tool call that has already changed the simulated state.

## Development progress

| Stage | Main change | Status |
| --- | --- | --- |
| **01** | Local Qwen prompting and initial context experiments | Completed |
| **02** | Structured tool calling and persistent simulated device state | Baseline evaluated |
| **02.1** | Python device-ID normalization and in-process JSON locking | Implemented and evaluated |
| **02.2** | Execution-honesty prompt safeguards; tool-description variant also tested | Implemented and evaluated |
| **02.3** | Independent Qwen3 0.6B claim extraction, Python verification, and one correction attempt | Evaluated |
| **02.4 · Current** | Structured execution-evidence feedback and one tool-free self-correction; 0.6B extractor + Python recheck | **Experimental; evaluated** |

## Benchmark results

The same **100 scenarios / 120 user turns** test device control, state queries, unsupported requests, ambiguity, conversation context, and execution honesty. Each scenario starts with isolated simulated state.

| Version | Pass | Partial | Fail | Verified action sequences | No unauthorized state changes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage 02 baseline | 52 | 12 | 36 | 14/35 | 96/100 |
| Stage 02.1 normalization | 73 | 7 | 20 | 33/35 | 96/100 |
| Stage 02.2 prompt safeguards | 73 | 16 | 11 | 33/35 | 99/100 |
| Stage 02.3 claim verification | 75 | 15 | 10 | 33/35 | 98/100 |
| **Stage 02.4 evidence-guided correction** | **76** | **17** | **7** | **33/35** | **98/100** |

*Pass/partial/fail are qualitative reviews, not deterministic accuracy scores. Action-sequence counts after Stage 02.1 credit verified device-ID normalization. These are individual local runs on a fixed challenge set; small differences are not statistically established improvements.*

### Stage 02.3: previous baseline

Across 120 responses, **87 were accepted unchanged**, **22 bypassed the keyword-based verifier**, and **11 triggered a correction attempt**. Of those 11, **5 revisions were accepted** and **6 ended in a conservative fallback**.

**Promising:** The verifier caught fabricated completion claims in **HM092–HM094**, where the main agent claimed to have performed actions without successful tool execution.

**Still unresolved:** It sometimes confuses *locked* with *unlocked*, rejects valid confirmations, mishandles prior-turn evidence, and misses unsupported-device assertions. In **HM059/HM060**, the underlying agent performed unauthorized actions; post-response checking cannot undo them.

[Full Stage 02.3 JSONL trace](experiments/results/stage_02_eval_20261020_225733.jsonl) · [Stage 02.2 trace](experiments/results/stage_02_eval_20261018_204026.jsonl) · [Stage 02 baseline report](experiments/stage_02_evaluation_report.md)

### Stage 02.4: structured evidence-guided self-correction (3 November 2026)

**Research question:** Can structured feedback about actual tool execution help a small agentic language model correct unsupported responses without making additional tool calls?

The initial **Qwen3 1.7B** LangChain agent still executes the same four simulated home tools. **Qwen3 0.6B** extracts claims and deterministic **Python** compares them against tool receipts. If an answer is unsupported, the main **1.7B** model receives the original request/answer, current and prior execution receipts, and unsupported claims, then generates **one tool-free revision**. The extractor and Python check the revision against the *same* receipts; an unsupported second attempt produces a conservative fallback. The correction stage is never bound to tools.

Across **100 scenarios / 120 user turns**, 88 original answers were accepted, 21 skipped the keyword filter, **11** triggered correction, **3** corrections were accepted and **8** ended with a fallback. The qualitative LLM-as-judge review assigned **76 pass / 17 partial / 7 fail**, compared with 75 / 15 / 10 for Stage 02.3. Expected write sequences remained **33/35**, and **98/100** scenarios had no unrequested state changes.

**Interpretation:** The aggregate difference is small and based on separate local runs; it is **not** evidence of a causal improvement attributable solely to more structured feedback. HM038 demonstrated a helpful correction, while HM009/HM040/HM045/HM084 illustrated false rejections caused by extractor errors (negation or numeric types). HM099 showed that a second extraction returning an empty claim list can miss a fabricated 50°C completion claim. HM059/HM060 still demonstrate that post-execution honesty checks do not prevent unwanted initial actions.

**Reproduce this version (default 0.6B extractor):**

```bash
python src/02_4_evidence_self_correction_agent.py
python src/03_run_evidence_correction_evaluation.py --ids HM009 HM034 HM038 HM045 HM065 HM099
python src/03_run_evidence_correction_evaluation.py
python src/04_export_evidence_correction_csv.py experiments/results/stage_02_eval_20261103_163750.jsonl
```

[Stage 02.4 agent](src/02_4_evidence_self_correction_agent.py) · [Evaluation runner](src/03_run_evidence_correction_evaluation.py) · [Raw 100-scenario JSONL trace](experiments/results/stage_02_eval_20261103_163750.jsonl)

**Next experiment (not yet implemented):** a hybrid validator that uses 0.6B for first-pass extraction, Python for receipt matching, and selective 1.7B semantic adjudication of ambiguous or incompletely extracted claims.

## Run locally

Requires **Python**, **Ollama**, and the Python packages used by LangChain and its Ollama integration.

```bash
# From the GharMind repository root
python -m pip install langchain langchain-core langchain-ollama
ollama pull qwen3:1.7b
ollama pull qwen3:0.6b

# Current Stage 02.4 (tool-free correction)
python src/02_4_evidence_self_correction_agent.py

# Preserved Stage 02.3 baseline
python src/02_3_claim_verifier_agent.py
```

Ollama must be running locally. **The NLI/DeBERTa model is not part of Stage 02.3.**

### Reproduce the evaluation

```bash
# Quick check: previously fabricated execution claims
python src/03_run_claim_evaluation.py --ids HM092 HM093 HM094

# Full 100-scenario benchmark
python src/03_run_claim_evaluation.py
```

The runner reuses the [existing benchmark](src/03_run_evaluation.py), writes timestamped JSONL to `experiments/results/`, and records tool calls, state changes, extracted claims, decisions, and retries.

To run the earlier **Stage 02.2 agent** independently:

```bash
python src/02_2_tool_agent_qwen_execution_honesty.py
```

## Project files

| Path | Purpose |
| --- | --- |
| [`src/02_3_claim_verifier_agent.py`](src/02_3_claim_verifier_agent.py) | Preserved Stage 02.3 agent + Qwen3 0.6B extractor |
| [`src/03_run_claim_evaluation.py`](src/03_run_claim_evaluation.py) | Stage 02.3 evaluation entry point |
| [`src/02_4_evidence_self_correction_agent.py`](src/02_4_evidence_self_correction_agent.py) | Stage 02.4 structured feedback and tool-free correction |
| [`src/03_run_evidence_correction_evaluation.py`](src/03_run_evidence_correction_evaluation.py) | Stage 02.4 reproducibility runner |
| [`src/04_export_evidence_correction_csv.py`](src/04_export_evidence_correction_csv.py) | Stage 02.4 JSONL-to-CSV exporter |
| [`src/02_2_tool_agent_qwen_execution_honesty.py`](src/02_2_tool_agent_qwen_execution_honesty.py) | Preserved prompt-only baseline |
| [`src/home_tools.py`](src/home_tools.py) | Simulated device read/write functions |
| [`experiments/stage_02_benchmark_100.jsonl`](experiments/stage_02_benchmark_100.jsonl) | Fixed 100-scenario challenge set |
| [`experiments/results/`](experiments/results/) | Raw execution and evaluation traces |

## Next steps

1. **Evaluate hybrid semantic claim validation:** test selective Qwen3 1.7B adjudication alongside 0.6B extraction and Python receipt verification.
2. **Refine the Qwen3 0.6B extractor prompt:** negation, temporal references, and unknown devices.
3. **Improve coverage and calibration:** verify relevant responses without keyword misses; quantify missed fabrications and false rejections.
4. **Strengthen pre-execution controls:** prevent unsupported or ambiguous commands from changing state.
5. **Then extend memory:** persistent conversation history, retrieval, and context management, followed by more advanced agent workflows.

GharMind prioritizes **measurable reliability improvements and reproducible experiments** over claims of production readiness.
