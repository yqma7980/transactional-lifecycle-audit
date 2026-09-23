"""Sealed-spec checks and runtime metadata. Target imports occur only in load_native()."""
import ast
import hashlib
import importlib
import inspect
import json
import platform
import sys
from pathlib import Path

from observations import loads


class IdentityFailure(ValueError):
    pass


class AdmissionFailure(ValueError):
    pass


MODULES = {
    79: ('django', 'django.db.models.fields.files', 'django.db.models.base', 'django.db.models.fields'),
    80: ('celery', 'celery.backends.base'),
    94: ('celery', 'celery.worker.loops', 'celery.worker.consumer.consumer', 'celery.bootsteps'),
}
BINDINGS = {
    79: {'fieldfile_eq': ('django.db.models.fields.files', 'FieldFile.__eq__'),
         'fieldfile_getstate': ('django.db.models.fields.files', 'FieldFile.__getstate__'),
         'fieldfile_url': ('django.db.models.fields.files', 'FieldFile.url.fget'),
         'file_descriptor_get': ('django.db.models.fields.files', 'FileDescriptor.__get__'),
         'model_eq': ('django.db.models.base', 'Model.__eq__'),
         'field_eq': ('django.db.models.fields', 'Field.__eq__')},
    80: {'exception_to_python': ('celery.backends.base', 'Backend.exception_to_python'),
         'fixture_constructor': ('m003_s10_celery5500_fixture', 'paramexception.__init__')},
    94: {'synloop': ('celery.worker.loops', 'synloop'),
         'call_soon': ('celery.worker.consumer.consumer', 'Consumer.call_soon'),
         'perform_pending_operations': ('celery.worker.consumer.consumer', 'Consumer.perform_pending_operations')},
}
SITES = {79: ('r79_restored_getattr', 'r79_url_storage'),
         80: ('r80_recipe_call', 'r80_constructor'), 94: ()}


def check(condition, message):
    if not condition:
        raise IdentityFailure(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_protocol(value):
    data = {k: v for k, v in value.items() if k != 'protocol_sha256'}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def absolute(value):
    check(type(value) is str and Path(value).is_absolute(), 'absolute path required')
    return str(Path(value).resolve())


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def file_map(value):
    check(type(value) is dict, 'file hash map required')
    result = {}
    for path, digest in value.items():
        key = absolute(path)
        check(key not in result, 'duplicate resolved path')
        check(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
              'lowercase SHA-256 required')
        check(sha256(key) == digest, 'file hash mismatch: ' + key)
        result[key] = digest
    return result


def validate_spec(spec, runtime=True, require_approval=True):
    """Read/hash/AST checks only; safe before approval without importing targets."""
    try:
        check(spec['schema'] == 'M003-S10-NATIVE-V2-SPEC-1', 'unsupported spec schema')
        if require_approval and spec['g3_parent_approved'] is not True:
            raise AdmissionFailure('parent G3 approval required; authoring is not admission')
        rank = spec['original_rank']
        check(type(rank) is int and rank in MODULES, 'unsupported rank')
        check(spec['cell'] in ('before-control', 'after-control', 'before-trigger', 'after-trigger'), 'invalid cell')
        version, history = spec['cell'].split('-')
        check(spec['history'] == history, 'history/cell mismatch')
        check(type(spec['run_id']) is str and bool(spec['run_id']), 'missing run ID')
        for name in ('cwd', 'source_root', 'fixture_root', 'recipe', 'protocol_path', 'environment_lock_path', 'executable'):
            spec[name] = absolute(spec[name])
        if runtime:
            check(spec['cwd'] == str(Path.cwd().resolve()), 'working-directory mismatch')
        check(not inside(spec['fixture_root'], spec['source_root']) and
              not inside(spec['source_root'], spec['fixture_root']), 'fixture and native trees must be disjoint')
        check(not inside(spec['recipe'], spec['source_root']), 'recipe cannot patch the native tree')
        check(sha256(spec['protocol_path']) == spec['protocol_file_sha256'], 'protocol file hash mismatch')
        protocol = loads(Path(spec['protocol_path']).read_text(encoding='utf-8'))
        check(canonical_protocol(protocol) == protocol['protocol_sha256'] == spec['protocol_sha256'],
              'canonical protocol hash mismatch')
        check(protocol['original_rank'] == rank and protocol['case_id'] == spec['case_id'], 'protocol/case mismatch')
        check(protocol[version + '_sha'] == spec['source_commit'], 'wrong source commit for cell')
        check(sha256(spec['environment_lock_path']) == spec['environment_lock_sha256'], 'environment lock mismatch')
        lock = loads(Path(spec['environment_lock_path']).read_text(encoding='utf-8'))
        check(lock['rank'] == rank and lock['status'] == 'ENVIRONMENT_AND_IMPORT_IDENTITY_FROZEN', 'environment not ready')
        locked = lock['versions'][version]
        for key in ('executable', 'source_root', 'fixture_root'):
            check(absolute(locked[key]) == spec[key], 'environment/spec path mismatch: ' + key)
        for key in ('source_commit', 'python_version', 'package_version', 'source_files', 'module_files', 'source_manifest_sha256'):
            check(locked[key] == spec[key], 'environment/spec identity mismatch: ' + key)
        check(lock['fixture_files'] == spec['fixture_files'], 'environment fixture identity mismatch')
        # This parent's lock names the protocol's FILE digest protocol_sha256.
        check(lock['protocol_sha256'] == spec['protocol_file_sha256'], 'environment protocol-file binding mismatch')
        check(sha256(spec['recipe']) == spec['recipe_sha256'] == protocol['runnable_recipe']['sha256'],
              'frozen recipe hash mismatch')
        spec['source_files'] = file_map(spec['source_files'])
        check(bool(spec['source_files']) and all(inside(p, spec['source_root']) for p in spec['source_files']),
              'production file outside sealed source root')
        spec['fixture_files'] = file_map(spec['fixture_files'])
        declared = {str((Path(spec['fixture_root']) / p).resolve()): text
                    for p, text in protocol['fixture_source_files'].items()}
        check(spec['fixture_files'].keys() == declared.keys(), 'fixture file set differs from protocol')
        for path, text in declared.items():
            check(inside(path, spec['fixture_root']) and Path(path).read_bytes() == text.encode('utf-8'),
                  'fixture bytes differ from frozen declaration')
        actual_fixture = {str(p.resolve()) for p in Path(spec['fixture_root']).rglob('*') if p.is_file()}
        check(actual_fixture == set(declared), 'extra/stale files in fixture root; shadowing forbidden')
        spec['module_files'] = {k: absolute(v) for k, v in spec['module_files'].items()}
        check(set(MODULES[rank]) <= set(spec['module_files']), 'required production module missing')
        for name, path in spec['module_files'].items():
            check(path in spec['source_files'], 'unhashed production module: ' + name)
        check(set(spec['code_bindings']) == set(BINDINGS[rank]), 'required native code bindings missing/extra')
        all_hashes = dict(spec['source_files'], **spec['fixture_files'])
        all_hashes[spec['recipe']] = spec['recipe_sha256']
        for key, binding in spec['code_bindings'].items():
            check((binding['module'], binding['qualname']) == BINDINGS[rank][key], 'wrong binding symbol: ' + key)
            binding['filename'] = absolute(binding['filename'])
            check(all_hashes.get(binding['filename']) == binding['sha256'], 'unsealed binding file')
            check(type(binding['firstlineno']) is int and binding['firstlineno'] > 0, 'invalid first line')
        check(set(spec['callsite_ids']) == set(SITES[rank]), 'missing/extra origin callsites')
        expected_site = {
            'r79_restored_getattr': (spec['recipe'], 'run', 37),
            'r79_url_storage': (spec['code_bindings'].get('fieldfile_url', {}).get('filename'), 'url', None),
            'r80_recipe_call': (spec['recipe'], 'run', 46),
            'r80_constructor': (spec['code_bindings'].get('exception_to_python', {}).get('filename'), 'exception_to_python', None),
        }
        for key, site in spec['callsite_ids'].items():
            site['filename'] = absolute(site['filename'])
            path, function, fixed_line = expected_site[key]
            check(site['filename'] == path and site['function'] == function, 'wrong callsite symbol/file')
            check(all_hashes.get(path) == site['sha256'], 'unsealed callsite file')
            line = site['lineno']
            check(type(line) is int and line > 0 and (fixed_line is None or fixed_line == line), 'wrong callsite line')
            text = Path(path).read_text(encoding='utf-8')
            check(line <= len(text.splitlines()), 'callsite outside file')
            nodes = ast.walk(ast.parse(text))
            check(any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function and
                      n.lineno <= line <= n.end_lineno for n in nodes), 'callsite outside declared function')
        if runtime:
            check(spec['executable'] == str(Path(sys.executable).resolve()) and
                  spec['python_version'] == platform.python_version(), 'interpreter mismatch')
        check(type(spec['package_version']) is str and bool(spec['package_version']), 'missing sealed package version')
        return protocol
    except (IdentityFailure, AdmissionFailure):
        raise
    except (KeyError, TypeError, ValueError, OSError, SyntaxError) as exc:
        raise IdentityFailure('invalid sealed spec: ' + str(exc)) from exc


def load_native(spec):
    """Called only by an explicitly parent-approved, supervised future native cell."""
    rank = spec['original_rank']
    package_name = 'django' if rank == 79 else 'celery'
    check(not any(k == package_name or k.startswith(package_name + '.') for k in sys.modules), 'stale target modules')
    sys.path[:0] = [spec['source_root'], spec['fixture_root']]
    package = importlib.import_module(package_name)
    if rank == 79:
        from django.conf import settings
        work = Path(spec['cwd'])
        check(not (work / 'state.sqlite3').exists() and not (work / 'media').exists(), 'stale Django cell state')
        settings.configure(INSTALLED_APPS=['m003_s10_django_fixture'],
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(work / 'state.sqlite3')}},
            MEDIA_ROOT=str(work / 'media'), MEDIA_URL='/s10-media/',
            DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
            SECRET_KEY='m003-s10-local-only', USE_TZ=False)
        package.setup()
    modules = {name: importlib.import_module(name) for name in spec['module_files']}
    actual = {name: str(Path(module.__file__).resolve()) for name, module in modules.items()}
    check(actual == spec['module_files'], 'native import origin mismatch')
    version = package.get_version() if rank == 79 else package.__version__
    check(version == spec['package_version'], 'package version mismatch')
    fixture_modules = {}
    for path in spec['fixture_files']:
        relative = Path(path).relative_to(spec['fixture_root']).with_suffix('')
        parts = relative.parts[:-1] if relative.name == '__init__' else relative.parts
        name = '.'.join(parts)
        module = importlib.import_module(name)
        fixture_modules[name] = str(Path(module.__file__).resolve())
        check(fixture_modules[name] == path, 'fixture import origin mismatch')
    observed = {}
    for name, binding in spec['code_bindings'].items():
        value = importlib.import_module(binding['module'])
        for token in binding['qualname'].split('.'):
            value = getattr(value, token)
        check(inspect.isfunction(value), 'binding is not an unchanged Python function: ' + name)
        code = value.__code__
        record = dict(binding, filename=str(Path(code.co_filename).resolve()), firstlineno=code.co_firstlineno)
        check(record == binding and value.__module__ == binding['module'], 'native code origin mismatch: ' + name)
        observed[name] = record
    file_map(spec['source_files'])
    file_map(spec['fixture_files'])
    result = dict(package_version=version, module_files=actual, fixture_modules=fixture_modules, code_bindings=observed)
    if rank == 79:
        result['configured_storage_backend'] = settings.DEFAULT_FILE_STORAGE
    return result
