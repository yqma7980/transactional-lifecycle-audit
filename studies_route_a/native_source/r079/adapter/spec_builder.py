"""Rank79 sealed-spec builder: text/hash/AST only, no target or recipe imports."""
import argparse
import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from identity import BINDINGS, check, sha256, validate_spec
from observations import loads

RUNTIME_FILES = ('driver.py', 'evaluator.py', 'observations.py', 'identity.py')


def function_node(path, qualname):
    node = ast.parse(Path(path).read_text(encoding='utf-8'))
    parts = qualname.split('.')
    if parts[-1] == 'fget':
        parts.pop()
    for token in parts:
        matches = [n for n in node.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == token]
        check(len(matches) == 1, 'cannot uniquely bind source symbol: ' + qualname)
        node = matches[0]
    check(isinstance(node, ast.FunctionDef), 'binding must be a function')
    return node


def build_rank79(environment_lock_path, protocol_path, recipe_path, cell, run_id, cwd, parent_approved=False):
    """Returns a JSON-ready spec. Does not create fixtures, import code or run a cell."""
    lock_path, protocol_path, recipe_path = [Path(p).resolve() for p in (environment_lock_path, protocol_path, recipe_path)]
    lock = loads(lock_path.read_text(encoding='utf-8'))
    protocol = loads(protocol_path.read_text(encoding='utf-8'))
    version, history = cell.split('-')
    sealed = lock['versions'][version]
    spec = {k: sealed[k] for k in ('executable', 'source_root', 'source_commit', 'fixture_root',
                                 'python_version', 'package_version', 'source_files', 'module_files', 'source_manifest_sha256')}
    spec.update(schema='M003-S10-NATIVE-V2-SPEC-1', original_rank=79, case_id=protocol['case_id'],
                run_id=run_id, cell=cell, history=history, cwd=str(Path(cwd).resolve()),
                protocol_path=str(protocol_path), protocol_file_sha256=sha256(protocol_path),
                protocol_sha256=protocol['protocol_sha256'], environment_lock_path=str(lock_path),
                environment_lock_sha256=sha256(lock_path), recipe=str(recipe_path), recipe_sha256=sha256(recipe_path),
                fixture_files=lock['fixture_files'], g3_parent_approved=parent_approved,
                collector_contract='TYPED_GRAMMAR_FIRST_GENERIC_INTEGRITY_V1',
                adapter_files={str(HERE / name): sha256(HERE / name) for name in RUNTIME_FILES})
    bindings = {}
    for key, (module, qualname) in BINDINGS[79].items():
        path = Path(spec['module_files'][module]).resolve()
        node = function_node(path, qualname)
        first = min([node.lineno] + [d.lineno for d in node.decorator_list])
        bindings[key] = dict(module=module, qualname=qualname, filename=str(path), firstlineno=first, sha256=sha256(path))
    spec['code_bindings'] = bindings
    path = bindings['fieldfile_url']['filename']
    url = function_node(path, 'FieldFile.url')
    returns = [n for n in ast.walk(url) if isinstance(n, ast.Return) and any(
        isinstance(a, ast.Attribute) and a.attr == 'storage' for a in ast.walk(n))]
    check(len(returns) == 1, 'url storage callsite not unique')
    spec['callsite_ids'] = {
        'r79_restored_getattr': dict(filename=str(recipe_path), function='run', lineno=37, sha256=sha256(recipe_path)),
        'r79_url_storage': dict(filename=path, function='url', lineno=returns[0].lineno, sha256=sha256(path))}
    validate_spec(spec, runtime=False, require_approval=False)
    return spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('environment-lock', 'protocol', 'recipe', 'cell', 'run-id', 'cwd', 'out'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--parent-approved', action='store_true', help='Only after independent parent G3 admission.')
    args = parser.parse_args()
    spec = build_rank79(args.environment_lock, args.protocol, args.recipe, args.cell, args.run_id,
                        args.cwd, parent_approved=args.parent_approved)
    with Path(args.out).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(spec, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'spec_written': str(Path(args.out).resolve()), 'g3_parent_approved': spec['g3_parent_approved'],
                      'target_imports': 0, 'target_runs': 0}))


if __name__ == '__main__':
    main()
