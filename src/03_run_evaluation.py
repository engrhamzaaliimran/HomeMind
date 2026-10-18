"""HomeMind Stage 02: run the committed interactive agent against 100 isolated scenarios.

Place this file at: HomeMind/src/03_run_evaluation.py
Place the companion dataset at: HomeMind/experiments/stage_02_benchmark_100.jsonl

From the HomeMind repository root, with your current virtual environment active:
    python src/03_run_evaluation.py --limit 5
    python src/03_run_evaluation.py

This runner deliberately DOES NOT change 02_tool_agent_qwen.py or its prompt/model.
It loads the existing agent setup (everything before the interactive while loop),
reproduces its current five-turn RAM-history logic, and isolates device state in a
separate temporary JSON file. Your own data/home_state.json is never rewritten.

Results are written incrementally as JSONL. No automatic LLM judge is invoked.
"""

import argparse
import ast
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
AGENT_FILE = ROOT / "src" / "02_tool_agent_qwen.py"
DEFAULT_DATASET = ROOT / "experiments" / "stage_02_benchmark_100.jsonl"
RESULTS_DIR = ROOT / "experiments" / "results"


def load_dataset(path):
    cases = []
    ids = set()
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            case = json.loads(line)
            if case["id"] in ids:
                raise ValueError(f"Repeated scenario ID at line {line_number}: {case['id']}")
            if not case.get("turns") or not case.get("initial_state"):
                raise ValueError(f"Invalid scenario at line {line_number}")
            ids.add(case["id"])
            cases.append(case)
    if not cases:
        raise ValueError("The benchmark dataset is empty")
    return cases


def load_existing_agent(source_path):
    """Run the EXACT existing agent's setup, without entering its interactive loop.

    We stop before its top-level ``while True``. This deliberately uses the
    source-of-truth model configuration, system prompt, and tool definitions.
    It is intended for your trusted local source file, not arbitrary code.
    """
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    setup_nodes = []
    found_loop = False
    for node in tree.body:
        if isinstance(node, ast.While):
            found_loop = True
            break
        setup_nodes.append(node)
    if not found_loop:
        raise RuntimeError("Expected a top-level while loop in 02_tool_agent_qwen.py; inspect its layout")
    setup_code = compile(
        ast.fix_missing_locations(ast.Module(body=setup_nodes, type_ignores=[])),
        filename=str(source_path),
        mode="exec",
    )
    namespace = {"__file__": str(source_path), "__name__": "homemind_benchmark_setup"}
    exec(setup_code, namespace)
    needed = ("agent", "llm", "tools", "system_prompt", "MAX_TURNS")
    missing = [key for key in needed if key not in namespace]
    if missing:
        raise RuntimeError(f"Agent setup does not export: {missing}")
    if int(namespace["MAX_TURNS"]) != 5:
        raise RuntimeError(
            f"This benchmark targets five-turn RAM context; found MAX_TURNS={namespace['MAX_TURNS']}"
        )
    if getattr(namespace["agent"], "checkpointer", None) is not None:
        raise RuntimeError("Expected current Stage 02 RAM-only agent, not a checkpointed memory agent")
    return namespace, hashlib.sha256(source.encode("utf-8")).hexdigest()


def parse_tool_content(content):
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (TypeError, ValueError):
            return content
    return content


def plain_content(content):
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def read_state(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path, state):
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def collect_generated_messages(messages):
    """Keep genuine AIMessage.tool_calls separate from generated text."""
    from langchain_core.messages import AIMessage, ToolMessage

    steps = []
    calls = []
    results = []
    for message in messages:
        if isinstance(message, AIMessage):
            model_calls = []
            for item in message.tool_calls:
                info = {
                    "name": item.get("name"),
                    "args": item.get("args"),
                    "id": item.get("id"),
                }
                calls.append(info)
                model_calls.append(info)
            steps.append({
                "message_type": "ai",
                "text": plain_content(message.content),
                "tool_calls": model_calls,
                "invalid_tool_calls": getattr(message, "invalid_tool_calls", []),
                "usage_metadata": getattr(message, "usage_metadata", None),
            })
        elif isinstance(message, ToolMessage):
            info = {
                "name": getattr(message, "name", None),
                "tool_call_id": getattr(message, "tool_call_id", None),
                "content": plain_content(message.content),
                "parsed_content": parse_tool_content(message.content),
                "status": getattr(message, "status", None),
            }
            results.append(info)
            steps.append({"message_type": "tool", **info})
        else:
            steps.append({
                "message_type": type(message).__name__,
                "text": plain_content(getattr(message, "content", "")),
            })
    return steps, calls, results


def run_turn(agent, history, user_text, max_turns, state_path):
    from langchain_core.messages import HumanMessage

    before_state = read_state(state_path)
    messages = history + [HumanMessage(content=user_text)]
    started = time.perf_counter()
    try:
        result = agent.invoke({"messages": messages})
        response_messages = result["messages"]
        # Identical slicing to the current interactive implementation.
        new_messages = response_messages[len(messages):]
        steps, tool_calls, tool_results = collect_generated_messages(new_messages)
        answer = plain_content(response_messages[-1].content)

        history = response_messages
        user_positions = [
            idx for idx, msg in enumerate(history)
            if isinstance(msg, HumanMessage)
        ]
        if len(user_positions) > max_turns:
            history = history[user_positions[-max_turns]:]

        return {
            "user": user_text,
            "final_response": answer,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "agent_messages": steps,
            "state_before": before_state,
            "state_after": read_state(state_path),
            "history_user_turns_after": sum(isinstance(msg, HumanMessage) for msg in history),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "error": None,
        }, history
    except Exception as exc:
        return {
            "user": user_text,
            "final_response": None,
            "tool_calls": [],
            "tool_results": [],
            "agent_messages": [],
            "state_before": before_state,
            "state_after": read_state(state_path),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }, history


def values_match(actual, expected):
    # Handles 20 == 20.0 but does not confuse True with 1.
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(actual - expected) < 1e-6
    return actual == expected


def get_nested(state, dotted_key):
    obj = state
    for part in dotted_key.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return False, None
        obj = obj[part]
    return True, obj


def required_call_matching(required, observed):
    """Match expected calls in any order; each actual call can match at most once."""
    remaining = list(observed)
    found = []
    missing = []
    for expected in required:
        matched_idx = None
        for idx, actual in enumerate(remaining):
            if expected.get("name") != actual.get("name"):
                continue
            expected_args = expected.get("args", {})
            actual_args = actual.get("args") or {}
            if not isinstance(actual_args, dict):
                continue
            if actual_args.keys() == expected_args.keys() and all(
                values_match(actual_args[key], val)
                for key, val in expected_args.items()
            ):
                matched_idx = idx
                break
        if matched_idx is None:
            missing.append(expected)
        else:
            found.append(remaining.pop(matched_idx))
    return found, missing


def state_changes(before, after, prefix=""):
    """List individual leaf-level changes, including any unexpected side effects."""
    changed = {}
    keys = set(before.keys()) | set(after.keys())
    for key in sorted(keys):
        full_key = f"{prefix}.{key}" if prefix else key
        if key not in before or key not in after:
            changed[full_key] = {
                "before": before.get(key, "<missing>"),
                "after": after.get(key, "<missing>"),
            }
        elif isinstance(before[key], dict) and isinstance(after[key], dict):
            changed.update(state_changes(before[key], after[key], full_key))
        elif not values_match(before[key], after[key]):
            changed[full_key] = {"before": before[key], "after": after[key]}
    return changed


def deterministic_checks(expected, turns, final_state):
    target = turns[-1]
    required = expected.get("required_tool_calls_on_target", [])
    observed_calls = target.get("tool_calls", [])
    found, missing = required_call_matching(required, observed_calls)
    expected_names = Counter(call["name"] for call in required)
    observed_names = Counter(call.get("name") for call in observed_calls)
    names_found = all(observed_names[name] >= count for name, count in expected_names.items())
    state_checks = {}
    for dotted_key, expected_val in expected.get("expected_final_state_fields", {}).items():
        exists, value = get_nested(final_state, dotted_key)
        state_checks[dotted_key] = {
            "pass": exists and values_match(value, expected_val),
            "expected": expected_val,
            "actual": value if exists else "<missing>",
        }
    # Verify that target-turn writes affect only the fields requested by the user.
    delta = state_changes(target["state_before"], target["state_after"])
    expected_state_keys = set(expected.get("expected_final_state_fields", {}))
    unexpected_delta = {
        key: value for key, value in delta.items()
        if key not in expected_state_keys
    }
    write_call_names = {"set_temperature", "set_light", "set_door_lock"}
    matched_writes = [call for call in found if call.get("name") in write_call_names]
    results_by_call_id = {
        item.get("tool_call_id"): item.get("parsed_content")
        for item in target.get("tool_results", [])
    }
    verified_writes = [
        call for call in matched_writes
        if isinstance(results_by_call_id.get(call.get("id")), dict)
        and results_by_call_id[call.get("id")].get("success") is True
    ]
    checks = {
        "required_calls_found": found,
        "required_calls_missing": missing,
        "required_tool_names_pass": names_found,
        "required_calls_pass": not missing,  # Tool names AND exact argument keys/values.
        "expected_final_state_field_checks": state_checks,
        "expected_final_state_fields_pass": all(x["pass"] for x in state_checks.values()),
        "target_state_changes": delta,
        "unexpected_target_state_changes": unexpected_delta,
        "no_unrequested_state_mutations_pass": not unexpected_delta,
        "verified_expected_writes_count": len(verified_writes),
        "expected_write_results_pass": (
            len(verified_writes) == len(matched_writes) ==
            sum(call["name"] in write_call_names for call in required)
            if any(call["name"] in write_call_names for call in required)
            else None
        ),
        "target_state_unchanged_pass": (
            target["state_before"] == target["state_after"]
            if expected.get("no_state_change_on_target") else None
        ),
        "target_no_tool_calls_pass": (
            len(target.get("tool_calls", [])) == 0
            if expected.get("no_tool_calls_on_target") else None
        ),
    }
    return checks


def run_case(case, agent, max_turns, state_path, prompt_fingerprint, agent_fingerprint):
    from datetime import datetime, timezone
    initial = copy.deepcopy(case["initial_state"])
    save_state(state_path, initial)
    history = []
    turn_runs = []
    started = time.perf_counter()
    for turn in case["turns"]:
        result, history = run_turn(agent, history, turn["user"], max_turns, state_path)
        turn_runs.append(result)
        if result["error"]:
            # Don't turn a broken setup into an apparently successful follow-up.
            break
    final_state = read_state(state_path)
    complete = len(turn_runs) == len(case["turns"]) and not any(t["error"] for t in turn_runs)
    return {
        "id": case["id"],
        "category": case["category"],
        "description": case.get("description", ""),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed" if complete else "error",
        "agent_source_sha256": agent_fingerprint,
        "system_prompt_sha256": prompt_fingerprint,
        "initial_state": initial,
        "turns": turn_runs,
        "target_turn_index": len(case["turns"]) - 1,
        "expected": case["expected"],
        "final_state": final_state,
        "checks": deterministic_checks(case["expected"], turn_runs, final_state) if complete else None,
        "total_elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def arguments():
    p = argparse.ArgumentParser(description="Run HomeMind Stage 02 agent benchmark")
    p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    p.add_argument("--output", type=Path, help="Results JSONL path (default: timestamped file under experiments/results)")
    p.add_argument("--limit", type=int, help="Run first N selected cases for a smoke test")
    p.add_argument("--category", help="Run only one category, such as conversation_context")
    p.add_argument("--ids", nargs="+", help="Run selected IDs, for example --ids HM001 HM076")
    p.add_argument("--resume", action="store_true", help="Append to an existing --output, skipping completed IDs; requires matching agent and prompt")
    return p.parse_args()


def main():
    args = arguments()
    source_path = AGENT_FILE.resolve()
    dataset_path = args.dataset.resolve()
    if not source_path.is_file():
        raise SystemExit(f"Agent source not found: {source_path}")
    if not dataset_path.is_file():
        raise SystemExit(f"Dataset not found: {dataset_path}")
    cases = load_dataset(dataset_path)
    dataset_fingerprint = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    if args.category:
        cases = [case for case in cases if case["category"] == args.category]
    if args.ids:
        keep = set(args.ids)
        cases = [case for case in cases if case["id"] in keep]
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be >= 1")
        cases = cases[:args.limit]
    if not cases:
        raise SystemExit("No cases match the selected criteria")

    output = args.output
    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = RESULTS_DIR / f"stage_02_eval_{timestamp}.jsonl"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.resume:
        raise SystemExit(f"Results file already exists: {output}. Use a different --output or --resume.")
    if args.resume and args.output is None:
        raise SystemExit("--resume requires an explicit --output")

    print("Loading the current Stage 02 agent without its interactive input loop...")
    sys.path.insert(0, str(source_path.parent))
    namespace, agent_fingerprint = load_existing_agent(source_path)
    import home_tools  # The same module imported by 02_tool_agent_qwen.py
    if home_tools.set_light.__globals__.get("STATE_FILE") is not home_tools.STATE_FILE:
        raise RuntimeError("Could not verify home_tools.STATE_FILE binding")
    prompt_fingerprint = hashlib.sha256(namespace["system_prompt"].encode("utf-8")).hexdigest()
    model = namespace["llm"]
    metadata = {
        "agent_source_sha256": agent_fingerprint,
        "system_prompt_sha256": prompt_fingerprint,
        "dataset_sha256": dataset_fingerprint,
        "model": getattr(model, "model", None),
        "model_parameters": {
            key: getattr(model, key, None)
            for key in ("temperature", "reasoning", "num_predict", "num_ctx")
        },
        "max_turns": int(namespace["MAX_TURNS"]),
        "tools": [tool.name for tool in namespace["tools"]],
    }

    done = set()
    if args.resume and output.is_file():
        with output.open("r", encoding="utf-8") as prior:
            for line in prior:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("agent_source_sha256") != agent_fingerprint or record.get("system_prompt_sha256") != prompt_fingerprint:
                    raise SystemExit("Cannot resume: agent source or prompt changed since prior run")
                done.add(record["id"])
    selected = [case for case in cases if case["id"] not in done]
    print("Model:", metadata["model"], "| tools:", ", ".join(metadata["tools"]))
    print("Five-turn RAM memory; fresh history and home-state fixture for each scenario")
    print("Selected scenarios:", len(selected), "| estimated LLM requests:", sum(len(c["turns"]) for c in selected))
    print("Results:", output)
    if not selected:
        print("Nothing to run: all selected IDs are already present")
        return

    # Crucial isolation: Tools point to a disposable test state, not your own home_state.json.
    original_state_path = home_tools.STATE_FILE
    with tempfile.TemporaryDirectory(prefix="homemind-stage02-eval-") as tempdir:
        test_state_path = Path(tempdir) / "home_state.json"
        home_tools.STATE_FILE = test_state_path
        try:
            mode = "a" if args.resume else "w"
            with output.open(mode, encoding="utf-8") as results_file:
                for number, case in enumerate(selected, 1):
                    record = run_case(
                        case, namespace["agent"], namespace["MAX_TURNS"],
                        test_state_path, prompt_fingerprint, agent_fingerprint,
                    )
                    record["run_configuration"] = metadata
                    results_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    results_file.flush()  # Preserve completed scenarios if you stop the run.
                    check = record.get("checks") or {}
                    response = record["turns"][-1]["final_response"] if record["turns"] else "<no response>"
                    print(f"[{number:03d}/{len(selected):03d}] {case['id']} {case['category']} "
                          f"status={record['status']} tools={check.get('required_calls_pass')} "
                          f"state={check.get('expected_final_state_fields_pass')} "
                          f"time={record['total_elapsed_seconds']:.1f}s")
                    if record["status"] == "error":
                        print("    ERROR:", record["turns"][-1]["error"])
        finally:
            home_tools.STATE_FILE = original_state_path
    print("\nFinished. Upload this JSONL file to ChatGPT for qualitative judging:")
    print(output)


if __name__ == "__main__":
    main()