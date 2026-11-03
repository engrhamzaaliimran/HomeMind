"""Run the fixed 100-scenario GharMind benchmark with Stage 02.4.

Usage:
    python src/03_run_evidence_correction_evaluation.py
    python src/03_run_evidence_correction_evaluation.py --ids HM009 HM034 HM038 HM045 HM065 HM099
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gharmind_original_benchmark', ROOT / '03_run_evaluation.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
benchmark.AGENT_FILE = ROOT / '02_4_evidence_self_correction_agent.py'
_original_run_turn = benchmark.run_turn


def run_turn_with_audit(agent, history, user_text, max_turns, state_path):
    record, new_history = _original_run_turn(agent, history, user_text, max_turns, state_path)
    record['claim_verification'] = (
        dict(getattr(agent, 'last_verification', {}) or {})
        if not record.get('error') else {'error': record['error']})
    return record, new_history


benchmark.run_turn = run_turn_with_audit
if __name__ == '__main__':
    benchmark.main()
