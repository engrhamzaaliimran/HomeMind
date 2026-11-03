"""Export the complete GharMind Stage 02.4 JSONL trace to per-turn CSV."""
import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('jsonl', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    dst = args.output or args.jsonl.with_suffix('.csv')
    columns = ['scenario_id', 'category', 'turn_index', 'target_turn', 'user_request',
               'original_response', 'final_response', 'decision', 'revision_attempts',
               'recovery_calls', 'first_extraction', 'first_unsupported',
               'revision', 'second_extraction', 'second_unsupported',
               'second_extraction_empty', 'tool_calls', 'tool_results',
               'tool_evidence', 'target_state_changes', 'unexpected_target_state_changes',
               'scenario_status', 'checks_json', 'turn_json']
    count = 0
    with args.jsonl.open(encoding='utf-8') as src, dst.open('w', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=columns)
        writer.writeheader()
        for line in src:
            if not line.strip():
                continue
            scenario = json.loads(line)
            turns = scenario.get('turns') or []
            for i, turn in enumerate(turns):
                audit = turn.get('claim_verification') or {}
                checks = scenario.get('checks') or {}
                dump = lambda x: json.dumps(x, ensure_ascii=False, default=str)
                writer.writerow({
                    'scenario_id': scenario.get('id', ''),
                    'category': scenario.get('category', ''),
                    'turn_index': i,
                    'target_turn': i == scenario.get('target_turn_index', len(turns)-1),
                    'user_request': turn.get('user', ''),
                    'original_response': audit.get('original_response', ''),
                    'final_response': turn.get('final_response', ''),
                    'decision': audit.get('decision', ''),
                    'revision_attempts': audit.get('revision_attempts', 0),
                    'recovery_calls': audit.get('recovery_calls', 0),
                    'first_extraction': dump(audit.get('first_extraction')),
                    'first_unsupported': dump(audit.get('first_unsupported')),
                    'revision': audit.get('revision', ''),
                    'second_extraction': dump(audit.get('second_extraction')),
                    'second_unsupported': dump(audit.get('second_unsupported')),
                    'second_extraction_empty': audit.get('second_extraction_empty', ''),
                    'tool_calls': dump(turn.get('tool_calls')),
                    'tool_results': dump(turn.get('tool_results')),
                    'tool_evidence': dump(audit.get('tool_evidence')),
                    'target_state_changes': dump(checks.get('target_state_changes')),
                    'unexpected_target_state_changes': dump(checks.get('unexpected_target_state_changes')),
                    'scenario_status': scenario.get('status', ''),
                    'checks_json': dump(checks),
                    'turn_json': dump(turn),
                })
                count += 1
    print(f'Exported {count} turns to {dst}')


if __name__ == '__main__':
    main()
