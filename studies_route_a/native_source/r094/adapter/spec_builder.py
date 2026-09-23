"""Static Celery recovery spec builder; reads/hash/AST only, no target imports."""
import argparse
import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from identity import ADMITTED_RANK, BINDINGS, check, sha256, validate_spec
from observations import loads

RUNTIME_FILES = ('driver.py', 'evaluator.py', 'observations.py', 'identity.py')


def function_node(path, qualname):
    node = ast.parse(Path(path).read_text(encoding='utf-8'))
    for token in qualname.split('.'):
        matches = [n for n in node.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == token]
        check(len(matches) == 1, 'cannot uniquely bind source symbol: ' + qualname)
        node = matches[0]
    check(isinstance(node, ast.FunctionDef), 'binding must be function')
    return node


def build_rank80(environment_lock_path, protocol_path, recipe_path, cell, run_id, cwd, parent_approved=False):
    return build(80, environment_lock_path, protocol_path, recipe_path, cell, run_id, cwd, parent_approved)


def build_rank94(environment_lock_path, protocol_path, recipe_path, cell, run_id, cwd, parent_approved=False):
    return build(94, environment_lock_path, protocol_path, recipe_path, cell, run_id, cwd, parent_approved)


def build(rank, environment_lock_path, protocol_path, recipe_path, cell, run_id, cwd, parent_approved=False):
    check(type(rank) is int and rank == ADMITTED_RANK, 'wrong per-case adapter')
    check(cell in ('before-control', 'after-control', 'before-trigger', 'after-trigger'), 'invalid cell')
    lock_path, protocol_path, recipe_path = [Path(p).resolve() for p in
                                            (environment_lock_path, protocol_path, recipe_path)]
    lock = loads(lock_path.read_text(encoding='utf-8'))
    protocol = loads(protocol_path.read_text(encoding='utf-8'))
    version, history = cell.split('-')
    sealed = lock['versions'][version]
    spec = {k: sealed[k] for k in ('executable', 'executable_sha256', 'source_root', 'source_commit',
            'fixture_root', 'python_version', 'package_version', 'source_files', 'module_files',
            'source_manifest_sha256', 'dependency_paths', 'dependency_files')}
    spec.update(schema='M003-S10-CELERY-RECOVERY-SPEC-1', original_rank=rank, case_id=protocol['case_id'],
        run_id=run_id, cell=cell, history=history, cwd=str(Path(cwd).resolve()),
        protocol_path=str(protocol_path), protocol_file_sha256=sha256(protocol_path),
        protocol_sha256=protocol['protocol_sha256'], environment_lock_path=str(lock_path),
        environment_lock_sha256=sha256(lock_path), recipe=str(recipe_path), recipe_sha256=sha256(recipe_path),
        fixture_files=lock['fixture_files'], g3_parent_approved=parent_approved,
        source_manifest_path=str(Path(spec['source_root']).parent / 'SOURCE_MANIFEST.json'),
        collector_contract='TYPED_GRAMMAR_FIRST_GENERIC_INTEGRITY_V1',
        adapter_files={str(HERE / n): sha256(HERE / n) for n in RUNTIME_FILES})
    bindings = {}
    for key, (module, qualname) in BINDINGS[rank].items():
        if module == 'm003_s10_celery5500_fixture':
            path = Path(spec['fixture_root']) / (module + '.py')
        else:
            path = Path(spec['module_files'][module]).resolve()
        node = function_node(path, qualname)
        bindings[key] = dict(module=module, qualname=qualname, filename=str(path),
            firstlineno=min([node.lineno] + [d.lineno for d in node.decorator_list]), sha256=sha256(path))
    spec['code_bindings'] = bindings
    spec['callsite_ids'] = {}
    if rank == 80:
        recipe_run = function_node(recipe_path, 'run')
        calls = [n for n in ast.walk(recipe_run) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Attribute) and n.func.attr == 'exception_to_python']
        check(len(calls) == 1 and calls[0].lineno == 46, 'frozen recipe callsite mismatch')
        native_path = bindings['exception_to_python']['filename']
        native = function_node(native_path, 'Backend.exception_to_python')
        constructors = [n for n in ast.walk(native) if isinstance(n, ast.Call) and
                        isinstance(n.func, ast.Name) and n.func.id == 'cls']
        check(len(constructors) == 1, 'native constructor callsite ambiguous')
        spec['callsite_ids'] = {
            'r80_recipe_call': dict(filename=str(recipe_path), function='run', lineno=calls[0].lineno,
                                    sha256=sha256(recipe_path)),
            'r80_constructor': dict(filename=native_path, function='exception_to_python',
                                   lineno=constructors[0].lineno, sha256=sha256(native_path))}
    validate_spec(spec, runtime=False, require_approval=False)
    return spec


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('environment-lock', 'protocol', 'recipe', 'cell', 'run-id', 'cwd', 'out'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--parent-approved', action='store_true')
    a = p.parse_args()
    spec = build(ADMITTED_RANK, a.environment_lock, a.protocol, a.recipe, a.cell, a.run_id, a.cwd, a.parent_approved)
    with Path(a.out).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(spec, stream, ensure_ascii=True, allow_nan=False, indent=2)
        stream.write('\n')
    print(json.dumps({'spec_written': str(Path(a.out).resolve()), 'g3_parent_approved': spec['g3_parent_approved']}))


if __name__ == '__main__':
    main()
