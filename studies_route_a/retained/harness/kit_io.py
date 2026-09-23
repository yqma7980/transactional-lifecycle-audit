"""Task-local strict artifact I/O; no method-comparison imports."""
import hashlib
import json
from pathlib import Path

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def write_json_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, ensure_ascii=True, allow_nan=False)
        f.write('\n')

def pairs(values):
    out = {}
    for k, v in values:
        if k in out:
            raise ValueError('Duplicate JSON key: ' + k)
        out[k] = v
    return out

def bad_constant(x):
    raise ValueError('Non-finite JSON constant: ' + x)

def loads(text):
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant)

def read_json(path):
    return loads(Path(path).read_text(encoding='utf-8'))
