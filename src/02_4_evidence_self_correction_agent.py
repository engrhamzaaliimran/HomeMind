"""GharMind Stage 02.4: evidence-guided self-correction (NO tool recovery).

The initial Stage 02.2 agent can call tools normally. After an unsupported
claim, the same Qwen3 1.7B model gets evidence and revises its answer with
NO access to tools. Qwen3 0.6B extracts claims; Python verifies receipts.
"""
import ast
import json
import re
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

ROOT = Path(__file__).resolve().parent
BASE_PATH = ROOT / '02_3_claim_verifier_agent.py'


def load_stage_023():
    tree = ast.parse(BASE_PATH.read_text(encoding='utf-8'), filename=str(BASE_PATH))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.While):
            break
        nodes.append(node)
    namespace = {'__file__': str(BASE_PATH), '__name__': 'gharmind_stage_023_setup'}
    exec(compile(ast.fix_missing_locations(ast.Module(nodes, type_ignores=[])), str(BASE_PATH), 'exec'), namespace)
    return namespace


base = load_stage_023()
llm = base['llm']
tools = base['tools']  # Benchmark metadata for initial execution ONLY.
system_prompt = base['system_prompt']
extractor = base['extractor']
MAX_TURNS = base['MAX_TURNS']

CORRECTION_SYSTEM = """You are correcting a response from GharMind, a simulated-home assistant.
This is a RESPONSE-ONLY task. You have NO tools and MUST NOT propose or pretend
any tool invocation. Use only the supplied ORIGINAL USER REQUEST and ACTUAL
execution receipts. The original answer is not evidence that an action occurred.

Reason carefully about what the evidence actually proves:
- A successful write receipt proves an action executed; report its specific device
  and resulting value, including multi-device actions if multiple writes succeeded.
- A failed receipt or missing receipt does NOT prove an action succeeded.
- A successful get_home_state result is an actual state read; inspect its listed
  devices. A missing device must not be invented.
- 'unlocked' means locked=false; 'locked' means locked=true.
- Thermostat targets are numeric setpoints, never booleans or measured temperatures.
- Do not claim 'no tools were executed' if receipts include tool operations.
- Do not treat the validator's extracted claims as ground truth; the extractor
  can misread negation, plurals, and numerical values.
- If the original request is ambiguous or asks for unsupported functionality,
  do not invent a completed action. Explain the limitation or ask clarification.
- If evidence is insufficient or partial, say exactly what is verified and what
  is not, without claiming a missing action took place.

Return ONLY one concise user-facing response, in one or two sentences.
No analysis, JSON, tool syntax, or fabricated execution claims."""


def _extract_check(answer, current, prior):
    raw = extractor.invoke([
        SystemMessage(content=base['EXTRACT_PROMPT']),
        HumanMessage(content='Assistant answer:\n' + answer),
    ])
    claims = base['parse_json'](raw.content)
    unsupported = [c for c in claims if not base['verified_claim'](c, current, prior)]
    fake_tool_markup = bool(re.search(r'<\s*/?\s*tool\s*>', answer, re.I))
    return claims, unsupported, fake_tool_markup


def _fallback(current):
    successes = [r for r in current
                 if r.get('tool') in {'set_light', 'set_temperature', 'set_door_lock'}
                 and r.get('success') is True]
    if successes:
        return ('Sorry, I could not reliably verify my response. '
                'Some simulated device actions succeeded, but I cannot reliably '
                'summarize all of them here; please inspect the recorded device state.')
    return ('Sorry, I cannot confirm that this simulated-home request was completed '
            'from the available execution records. No further actions were attempted.')


class EvidenceCorrectionAgent:
    def __init__(self, underlying):
        self.underlying = underlying
        self.last_verification = {}

    @staticmethod
    def _replace(result, text):
        result = dict(result)
        result['messages'] = list(result['messages'])[:-1] + [AIMessage(content=text)]
        return result

    def invoke(self, inputs, **kwargs):
        original_result = self.underlying.invoke(inputs, **kwargs)
        incoming = list(inputs['messages'])
        generated = list(original_result['messages'])
        request = next((str(m.content) for m in reversed(incoming)
                        if isinstance(m, HumanMessage)), '')
        original = str(generated[-1].content).strip()
        current = base['tool_receipts'](generated[len(incoming):])
        prior = base['tool_receipts'](incoming)

        audit = {
            'stage': '02.4_evidence_self_correction',
            'original_response': original,
            'tool_evidence': current,
            'prior_tool_evidence': prior,
            'first_extraction': None,
            'first_unsupported': [],
            'revision': None,
            'second_extraction': None,
            'second_unsupported': [],
            'revision_attempts': 0,
            'recovery_allowed': False,
            'recovery_calls': 0,
            'decision': 'not_checked',
        }
        if not (base['HOME_CONTEXT'].search(request + ' ' + original) or current):
            audit['decision'] = 'skipped_non_home'
            self.last_verification = audit
            return original_result

        try:
            claims, unsupported, markup = _extract_check(original, current, prior)
            audit.update(first_extraction=claims, first_unsupported=unsupported,
                         fake_tool_markup=markup)
        except Exception as exc:
            audit.update(decision='extractor_error_fallback',
                         error=f'{type(exc).__name__}: {exc}')
            self.last_verification = audit
            return self._replace(original_result, _fallback(current))

        if not unsupported and not markup:
            audit['decision'] = 'accepted'
            self.last_verification = audit
            return original_result

        feedback = (
            'ORIGINAL USER REQUEST:\n' + request +
            '\n\nORIGINAL ASSISTANT RESPONSE (NOT EVIDENCE):\n' + original +
            '\n\nACTUAL CURRENT-TURN TOOL RECEIPTS:\n' + base['evidence_text'](current) +
            '\n\nPRIOR TOOL RECEIPTS (past actions only):\n' + base['evidence_text'](prior) +
            '\n\nCLAIMS THE EXTRACTOR COULD NOT VERIFY (may contain extractor mistakes):\n' +
            json.dumps(unsupported, ensure_ascii=False) +
            '\n\nFAKE TOOL MARKUP DETECTED: ' + str(markup) +
            '\n\nWrite a corrected final answer. Do not call tools.')
        try:
            audit['revision_attempts'] = 1
            revision = llm.invoke([
                SystemMessage(content=CORRECTION_SYSTEM),
                HumanMessage(content=feedback),
            ])
            correction = str(revision.content).strip()
            audit['revision'] = correction
            claims2, unsupported2, markup2 = _extract_check(correction, current, prior)
            audit.update(second_extraction=claims2, second_unsupported=unsupported2,
                         second_fake_tool_markup=markup2)
            if unsupported2 or markup2 or not correction:
                audit['decision'] = 'safe_fallback'
                correction = _fallback(current)
            else:
                audit['decision'] = 'accepted_after_tool_free_revision'
                audit['second_extraction_empty'] = len(claims2) == 0
        except Exception as exc:
            audit.update(decision='safe_fallback',
                         second_error=f'{type(exc).__name__}: {exc}')
            correction = _fallback(current)
        self.last_verification = audit
        return self._replace(original_result, correction)


agent = EvidenceCorrectionAgent(base['base']['agent'])
history = []

while True:
    command = input('\nGharMind command (q to quit): ').strip()
    if command.lower() == 'q':
        break
    if not command:
        continue
    result = agent.invoke({'messages': history + [HumanMessage(content=command)]})
    print('Validator:', agent.last_verification.get('decision'))
    print('GharMind:', result['messages'][-1].content)
    history = result['messages']
    human_positions = [i for i, m in enumerate(history) if isinstance(m, HumanMessage)]
    if len(human_positions) > MAX_TURNS:
        history = history[human_positions[-MAX_TURNS]:]
