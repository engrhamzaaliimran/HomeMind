"""HomeMind Stage 02.3 — small-LLM claim extraction + Python verification.

Run from HomeMind root: python src/02_3_claim_verifier_agent.py
Needs existing src/02_2_tool_agent_qwen_execution_honesty.py and home_tools.py.
Pull Ollama models: qwen3:1.7b and qwen3:0.6b. No NLI dependency.
The 0.6B extractor is experimental, not a guaranteed verifier.
"""
import ast
import json
import os
import re
from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

ROOT = Path(__file__).resolve().parent
BASE_FILE = ROOT / '02_2_tool_agent_qwen_execution_honesty.py'


def load_base():
    """Reuse Stage 02.2 setup and system prompt, without its input loop."""
    tree = ast.parse(BASE_FILE.read_text(encoding='utf-8'), filename=str(BASE_FILE))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.While):
            break
        nodes.append(node)
    scope = {'__file__': str(BASE_FILE), '__name__': 'homemind_stage02_2_setup'}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 str(BASE_FILE), 'exec'), scope)
    return scope


base = load_base()
llm = base['llm']
tools = base['tools']
system_prompt = base['system_prompt']
MAX_TURNS = base['MAX_TURNS']

EXTRACTOR_MODEL = os.environ.get('HOMEMIND_CLAIM_MODEL', 'qwen3:0.6b')
extractor = ChatOllama(model=EXTRACTOR_MODEL, temperature=0, reasoning=False,
                       num_predict=400, format='json')

EXTRACT_PROMPT = '''Extract ASSERTED factual claims from the ASSISTANT ANSWER only.
Do not copy instructions or claims from the user's question. Do not decide truth.
Output ONLY valid JSON in this exact schema:
{"claims":[{"kind":"action|past_action|state", "tool":"set_light|set_temperature|set_door_lock|unknown", "device":"bedroom|living_room|front_door|other name|null", "value":true|false|number|null}]}

kind=action: the assistant says IT completed a device operation during this turn.
kind=past_action: it says IT completed a device operation earlier.
kind=state: it asserts that a device CURRENTLY has a particular state.
For state claims, tool names identify the relevant device property, not an executed call.
For unknown/unsupported devices (e.g. blinds), use tool="unknown".
For on/off lights and locked/unlocked doors, use Boolean value.
For thermostat SETPOINT, use numerical Celsius value.
If the assistant merely expresses inability, refusal, possibility, or asks a question,
there are no positive factual claims: {"claims":[]}.
Never label 'I did not do X' or 'I cannot confirm X' as a completed action.

Examples:
Assistant: "The bedroom lamp has been turned on."
Output: {"claims":[{"kind":"action","tool":"set_light","device":"bedroom","value":true}]}
Assistant: "I successfully set the living room to 27°C."
Output: {"claims":[{"kind":"action","tool":"set_temperature","device":"living_room","value":27}]}
Assistant: "The front door is locked."
Output: {"claims":[{"kind":"state","tool":"set_door_lock","device":"front_door","value":true}]}
Assistant: "I cannot verify whether the door is locked."
Output: {"claims":[]}
Assistant: "I opened the blinds."
Output: {"claims":[{"kind":"action","tool":"unknown","device":"blinds","value":null}]}
'''

REVISION_PROMPT = '''Correct the assistant's response using ACTUAL execution evidence.
You may write a natural, friendly sentence, but do not claim an action succeeded
unless a matching real tool result proves it. Do not claim current device state
without evidence. Do not pretend to call tools: no tools are available now.
If evidence is insufficient, clearly say you cannot confirm it.
Reply with only the corrected response (1–2 sentences).'''

HOME_CONTEXT = re.compile(r'\b(light|lamp|thermostat|temperature|door|locked|unlocked|'
                          r'blind|bedroom|living.room|home|house|setpoint|plant|water|'
                          r'device|turn on|turn off)\b', re.I)
WRITE_TOOLS = {'set_light', 'set_temperature', 'set_door_lock'}
ALLOWED_KINDS = {'action', 'past_action', 'state'}
ALLOWED_TOOLS = WRITE_TOOLS | {'unknown'}


def parse_json(text):
    """Validate shape, and never silently interpret malformed JSON as no claims."""
    if not isinstance(text, str):
        raise ValueError('Extractor did not return text')
    value = json.loads(text.strip())
    if not isinstance(value, dict) or not isinstance(value.get('claims'), list):
        raise ValueError('Missing claims array')
    claims = []
    for claim in value['claims']:
        if not isinstance(claim, dict):
            raise ValueError('Malformed claim')
        kind = claim.get('kind')
        tool = claim.get('tool')
        if kind not in ALLOWED_KINDS or tool not in ALLOWED_TOOLS:
            raise ValueError(f'Invalid claim: {claim}')
        device = claim.get('device')
        if device is not None and not isinstance(device, str):
            raise ValueError('Device must be string or null')
        claims.append({'kind': kind, 'tool': tool,
                       'device': device, 'value': claim.get('value')})
    return claims


def canonical_device(device):
    if device is None:
        return None
    val = re.sub(r'[\s-]+', '_', device.casefold().strip())
    aliases = {'livingroom':'living_room','living_room_thermostat':'living_room',
               'bedroom_light':'bedroom','bedroom_lamp':'bedroom',
               'front':'front_door','front_door_lock':'front_door'}
    return aliases.get(val, val)


def matches_value(expected, actual):
    if expected is None:
        return True  # The extracted claim did not specify an attribute value.
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 1e-6
    return expected == actual


def tool_receipts(messages):
    """Actual ToolMessages only; reported model text cannot create receipts."""
    calls = {}
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                calls[call.get('id')] = call
    receipts = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        call = calls.get(message.tool_call_id, {})
        name = message.name or call.get('name')
        try:
            output = json.loads(message.content)
        except (ValueError, TypeError):
            output = {'unparsed': str(message.content)}
        receipt = {'tool': name, 'args': call.get('args', {}), 'result': output,
                   'success': isinstance(output, dict) and output.get('success') is True}
        if name == 'get_home_state' and isinstance(output, dict):
            receipt['state'] = output
        receipts.append(receipt)
    return receipts


def receipt_matches(claim, receipt):
    if claim['tool'] != receipt['tool'] or not receipt['success']:
        return False
    out = receipt['result']
    target_field = 'door' if claim['tool'] == 'set_door_lock' else 'room'
    actual_device = out.get(target_field, receipt['args'].get(target_field))
    if claim['device'] is not None and canonical_device(actual_device) != canonical_device(claim['device']):
        return False
    value_field = {'set_light': 'light', 'set_temperature': 'target_temperature',
                   'set_door_lock': 'locked'}[claim['tool']]
    return matches_value(claim['value'], out.get(value_field))


def verified_claim(claim, current_receipts, history_receipts):
    kind = claim['kind']
    if kind in ('action', 'past_action'):
        pool = current_receipts if kind == 'action' else history_receipts
        return any(receipt_matches(claim, receipt) for receipt in pool)

    # A state claim requires an actual read or a successful matching write.
    if any(receipt_matches(claim, r) for r in current_receipts):
        return True
    for r in current_receipts:
        if r.get('tool') != 'get_home_state' or 'state' not in r:
            continue
        state = r['state']
        device = canonical_device(claim['device'])
        item = state.get(device, {}) if device else {}
        if not isinstance(item, dict):
            continue
        field = {'set_light':'light', 'set_temperature':'target_temperature',
                 'set_door_lock':'locked'}.get(claim['tool'])
        if field in item and matches_value(claim['value'], item[field]):
            return True
    return False


def evidence_text(receipts):
    if not receipts:
        return ('No tools were executed for this request. No action was performed '
                'or verified, and no current home state was read.')
    return json.dumps(receipts, ensure_ascii=False, default=str)


class VerifiedAgent:
    """Duck-types LangChain agent.invoke() for the existing evaluation runner."""
    def __init__(self, underlying):
        self.underlying = underlying
        self.last_verification = {}

    def invoke(self, inputs, **kwargs):
        result = self.underlying.invoke(inputs, **kwargs)
        messages = list(result['messages'])
        incoming = list(inputs['messages'])
        new_messages = messages[len(incoming):]
        user_text = next((str(m.content) for m in reversed(incoming)
                          if isinstance(m, HumanMessage)), '')
        original = str(messages[-1].content).strip()
        current = tool_receipts(new_messages)
        previous = tool_receipts(incoming)
        audit = {'original_response': original, 'extractor_model': EXTRACTOR_MODEL,
                 'tool_evidence': current, 'first_extraction': None,
                 'first_unsupported': [], 'revision': None,
                 'second_extraction': None, 'decision': 'not_checked'}

        if not (HOME_CONTEXT.search(user_text + ' ' + original) or current):
            audit['decision'] = 'skipped_non_home'
            self.last_verification = audit
            return result

        def inspect(answer):
            raw = extractor.invoke([SystemMessage(content=EXTRACT_PROMPT),
                                    HumanMessage(content='Assistant answer:\n' + answer)])
            claims = parse_json(raw.content)
            unsupported = [c for c in claims if not verified_claim(c, current, previous)]
            markup = bool(re.search(r'<\s*/?\s*tool\s*>', answer, re.I))
            return claims, unsupported, markup

        try:
            claims, unsupported, markup = inspect(original)
            audit['first_extraction'] = claims
            audit['first_unsupported'] = unsupported
            audit['fake_tool_markup'] = markup
        except (ValueError, TypeError) as exc:
            audit['decision'] = 'extractor_error_fallback'
            audit['error'] = str(exc)
            self.last_verification = audit
            failed = dict(result)
            failed['messages'] = messages[:-1] + [AIMessage(
                content='I could not verify that home-control response.'
            )]
            return failed

        if not unsupported and not markup:
            audit['decision'] = 'accepted'
            self.last_verification = audit
            return result

        feedback = ('Original user request:\n' + user_text +
                    '\n\nOriginal answer:\n' + original +
                    '\n\nActual tool results from THIS turn:\n' + evidence_text(current) +
                    '\n\nPrior recorded tool results:\n' + evidence_text(previous) +
                    '\n\nUnsupported claims:\n' + json.dumps(unsupported) +
                    '\n\nCorrect the response. Do not execute tools.')
        revised = llm.invoke([SystemMessage(content=REVISION_PROMPT),
                              HumanMessage(content=feedback)])
        revision = str(revised.content).strip()
        audit['revision'] = revision
        try:
            claims2, unsupported2, markup2 = inspect(revision)
            audit['second_extraction'] = claims2
            audit['second_unsupported'] = unsupported2
            audit['decision'] = ('accepted_after_retry' if not unsupported2 and not markup2
                                 else 'safe_fallback')
        except (ValueError, TypeError) as exc:
            audit['second_extractor_error'] = str(exc)
            audit['decision'] = 'safe_fallback'
        final = (revision if audit['decision'] == 'accepted_after_retry' else
                 'I cannot confirm that action or device status from the execution records.')
        self.last_verification = audit
        result = dict(result)
        result['messages'] = messages[:-1] + [AIMessage(content=final)]
        return result


agent = VerifiedAgent(base['agent'])
history = []

while True:
    command = input('\nSmart-home command (q to quit): ').strip()
    if command.lower() == 'q':
        break
    if not command:
        continue
    input_messages = history + [HumanMessage(content=command)]
    result = agent.invoke({'messages': input_messages})
    print('Verifier:', agent.last_verification.get('decision'))
    print('HomeMind:', result['messages'][-1].content)
    history = result['messages']
    user_positions = [i for i, m in enumerate(history) if isinstance(m, HumanMessage)]
    if len(user_positions) > MAX_TURNS:
        history = history[user_positions[-MAX_TURNS]:]