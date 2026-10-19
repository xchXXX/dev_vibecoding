"""Example check adapter; replace this entry with the project's real checks."""
import json
import sys
from pathlib import Path
scope, output = json.loads(sys.argv[1]), Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)
inputs = json.loads(Path('candidate-config.json').read_text())['inputs']
failed = False
for ident in scope:
    source = Path(inputs[ident])
    value = json.loads(source.read_text())[ident]
    observation = {'acceptance_id': ident, 'input': str(source), 'actual': value,
                   'expected': True, 'status': 'pass' if value is True else 'fail'}
    with Path('.artifacts/executions.jsonl').open('a') as counter:
        counter.write(json.dumps(observation) + '\n')
    (output / f'{ident}.json').write_text(json.dumps(observation) + '\n')
    print(json.dumps(observation), flush=True)
    failed |= value is not True
sys.exit(1 if failed else 0)
