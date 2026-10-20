"""Stage 02.3 full benchmark: identical fixtures/scoring as 03_run_evaluation.py.

Run: python src/03_run_claim_evaluation.py --ids HM092 HM093 HM094
Then: python src/03_run_claim_evaluation.py
Output JSONL includes claim_verification on each turn.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('homemind_original_benchmark',
                                               ROOT / '03_run_evaluation.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
benchmark.AGENT_FILE = ROOT / '02_3_claim_verifier_agent.py'

original_run_turn = benchmark.run_turn


def run_turn_with_claims(agent, history, user_text, max_turns, state_path):
    record, updated_history = original_run_turn(
        agent, history, user_text, max_turns, state_path)
    record['claim_verification'] = (
        dict(getattr(agent, 'last_verification', {}) or {})
        if not record['error'] else {'error': record['error']}
    )
    return record, updated_history


benchmark.run_turn = run_turn_with_claims

if __name__ == '__main__':
    benchmark.main()