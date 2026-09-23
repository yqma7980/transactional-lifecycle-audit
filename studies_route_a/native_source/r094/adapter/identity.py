"""Sealed-spec checks and runtime metadata. Target imports occur only in load_native()."""
import ast
import hashlib
import importlib
import inspect
import json
import platform
import sys
from pathlib import Path
from types import CodeType, FunctionType, MemberDescriptorType, MethodType, ModuleType

from observations import loads


class IdentityFailure(ValueError):
    pass


class AdmissionFailure(ValueError):
    pass


MODULES = {
    79: ('django', 'django.db.models.fields.files', 'django.db.models.base', 'django.db.models.fields'),
    80: ('celery', 'celery.backends.base'),
    94: ('celery', 'celery.worker.loops', 'celery.worker.consumer.consumer', 'celery.bootsteps', 'celery.worker.state'),
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
         'perform_pending_operations': ('celery.worker.consumer.consumer', 'Consumer.perform_pending_operations'),
         'maybe_shutdown': ('celery.worker.state', 'maybe_shutdown')},
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


def _validate_v2_spec(spec, runtime=True, require_approval=True):
    """Read/hash/AST checks only; safe before approval without importing targets."""
    try:
        check(spec['schema'] == 'M003-S10-CELERY-RECOVERY-SPEC-1', 'unsupported spec schema')
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
    sys.path[:0] = [spec['source_root'], spec['fixture_root']] + spec['dependency_paths']
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
        _BOUND_FUNCTIONS[name] = value
    file_map(spec['source_files'])
    file_map(spec['fixture_files'])
    result = dict(package_version=version, module_files=actual, fixture_modules=fixture_modules, code_bindings=observed)
    if rank == 79:
        result['configured_storage_backend'] = settings.DEFAULT_FILE_STORAGE
    result['loaded_module_provenance'] = verify_loaded_targets(spec)
    if rank == 80:
        module = modules['celery.backends.base']
        check(module.BaseBackend.exception_to_python is module.Backend.exception_to_python,
              'BaseBackend must inherit the exact native method')
    if rank == 94:
        result['bootsteps_RUN'] = {'symbol': 'celery.bootsteps.RUN', 'value': modules['celery.bootsteps'].RUN,
                                 'source_file': spec['module_files']['celery.bootsteps']}
    return result

_BOUND_FUNCTIONS = {}
ADMITTED_RANK = 94
RECOVERY_ROOT = Path(__file__).resolve().parents[3]
PRIOR_SOURCE_ROOT = RECOVERY_ROOT.parent / 'M-2026-003_S10_G2G3_RECOVERY_20260907_052246'


def validate_spec(spec, runtime=True, require_approval=True):
    """Recovery admission adds standalone runtime and complete source/dependency binding."""
    try:
        check(type(spec['original_rank']) is int and spec['original_rank'] == ADMITTED_RANK,
              'wrong adapter rank')
        check(type(spec['g3_parent_approved']) is bool, 'approval must be boolean')
        check(spec['protocol_file_sha256'] == '18dac2117e71a91a26308c1609a446390dcbe709f00e8c8e5dc66795e32dde3f',
              'protocol is not the reviewed frozen r94 file')
        for key in ('cwd', 'executable', 'fixture_root', 'environment_lock_path'):
            check(inside(spec[key], RECOVERY_ROOT), 'recovery-owned path required: ' + key)
        check(not inside(spec['cwd'], Path(RECOVERY_ROOT) / 'sources'), 'output inside source evidence')
        protocol = _validate_v2_spec(spec, runtime=runtime, require_approval=require_approval)
        if ADMITTED_RANK == 80:
            path = spec['code_bindings']['exception_to_python']['filename']
            tree = ast.parse(Path(path).read_text(encoding='utf-8'))
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Backend')
            method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'exception_to_python')
            calls = [n for n in ast.walk(method) if isinstance(n, ast.Call) and
                     isinstance(n.func, ast.Name) and n.func.id == 'cls']
            check(len(calls) == 1 and spec['callsite_ids']['r80_constructor']['lineno'] == calls[0].lineno,
                  'constructor origin is not the exact source AST call')
        lock = loads(Path(spec['environment_lock_path']).read_text(encoding='utf-8'))
        sealed = lock['versions'][spec['cell'].split('-')[0]]
        for key in ('executable_sha256', 'dependency_paths', 'dependency_files'):
            check(sealed[key] == spec[key], 'environment/spec mismatch: ' + key)
        check(sha256(spec['executable']) == spec['executable_sha256'], 'executable hash mismatch')
        exe = Path(spec['executable'])
        check(exe.name.lower() == 'python.exe' and exe.parent.name.lower() != 'scripts',
              'direct standalone python.exe required, not venv redirector')
        check(not (exe.parent / 'pyvenv.cfg').exists() and not (exe.parent.parent / 'pyvenv.cfg').exists(),
              'venv launcher not admitted')
        if runtime:
            check(sys.prefix == sys.base_prefix and sys.flags.isolated == 1 and sys.flags.no_site == 1 and
                  sys.dont_write_bytecode, 'launch direct standalone Python with -I -S -B')
        paths = spec['dependency_paths']
        check(type(paths) is list and paths and all(type(p) is str for p in paths), 'dependency paths required')
        check(len(set(paths)) == len(paths), 'duplicate dependency path')
        for path in paths:
            check(absolute(path) == path and inside(path, RECOVERY_ROOT), 'unsealed dependency root')
            check(not inside(path, spec['source_root']) and not inside(path, spec['fixture_root']),
                  'dependency/source/fixture overlap')
        file_map(spec['dependency_files'])
        actual = {str(p.resolve()) for root in paths for p in Path(root).rglob('*') if p.is_file()}
        check(actual == set(spec['dependency_files']), 'missing/extra dependency inventory')
        check(all(any(inside(p, root) for root in paths) for p in actual), 'dependency file escapes roots')
        manifest_path = absolute(spec['source_manifest_path'])
        check(manifest_path == str(Path(spec['source_root']).parent / 'SOURCE_MANIFEST.json'),
              'source manifest must be adjacent to exact tree')
        check(sha256(manifest_path) == spec['source_manifest_sha256'], 'source manifest digest mismatch')
        manifest = loads(Path(manifest_path).read_text(encoding='utf-8'))
        check(type(manifest['rank']) is int and manifest['rank'] == ADMITTED_RANK and
              manifest['commit'] == spec['source_commit'] and manifest['all_git_blobs_match'] is True,
              'manifest source identity failed')
        expected_root = PRIOR_SOURCE_ROOT / 'sources' / ('r%03d' % ADMITTED_RANK) / 'git_transport' / 'acquisition_001'
        check(Path(spec['source_root']).resolve() == expected_root / spec['cell'].split('-')[0] / 'tree',
              'wrong recovered source root')
        check(absolute(manifest['source_root']) == spec['source_root'], 'manifest source path mismatch')
        required = {p for p in manifest['files'] if p.startswith('celery/')}
        required.update(protocol['environment_requirements']['full_tree_files_to_bind'])
        if ADMITTED_RANK == 94 and spec['cell'].startswith('before-'):
            required.discard('t/unit/test_loops.py')
        for relative in required:
            check(relative in manifest['files'], 'required source missing: ' + relative)
            entry = manifest['files'][relative]
            check(entry['mode'] in ('100644', '100755') and entry['type'] == 'blob' and
                  entry.get('symlink_materialized_as_text') is False and entry.get('git_lfs_pointer') is False,
                  'required native file has materialization hold: ' + relative)
            path = str((Path(spec['source_root']) / relative).resolve())
            check(spec['source_files'].get(path) == entry['sha256'], 'required source not sealed: ' + relative)
        for path, digest in spec['source_files'].items():
            relative = Path(path).relative_to(spec['source_root']).as_posix()
            check(manifest['files'][relative]['sha256'] == digest, 'source map not bound to Git manifest')
        check(not any(p.is_symlink() for p in Path(spec['source_root']).rglob('*')),
              'active source symlink not admitted')
        return protocol
    except (IdentityFailure, AdmissionFailure):
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise IdentityFailure('invalid recovery spec: ' + str(exc)) from exc


def verify_loaded_targets(spec):
    """Attest every loaded target submodule, including lazy imports during the recipe."""
    observed = {}
    for short in R94_COMPAT_MODULES['celery']:
        check('celery.' + short in sys.modules, 'missing declared compatibility module: ' + short)
    for name, module in list(sys.modules.items()):
        if name != 'celery' and not name.startswith('celery.'):
            continue
        check(isinstance(module, ModuleType), 'target is not a module: ' + name)
        if name in {'celery.' + n for n in R94_COMPAT_MODULES['celery']} or not module_namespace(module).get('__file__'):
            observed[name] = verify_native_generated_module(name, module, spec)
            continue
        path = str(Path(module_namespace(module)['__file__']).resolve())
        check(inside(path, spec['source_root']) and path in spec['source_files'], 'unsealed target origin: ' + name)
        check(sha256(path) == spec['source_files'][path], 'loaded target source drift: ' + name)
        observed[name] = path
    for name, value in _BOUND_FUNCTIONS.items():
        binding = spec['code_bindings'][name]
        current = importlib.import_module(binding['module'])
        for token in binding['qualname'].split('.'):
            current = getattr(current, token)
        check(current is value, 'native method changed during cell: ' + name)
    return observed


# These identical declarations/files belong to the frozen r94 before/after pair only.
R94_COMPAT_MODULES = {'celery': {
    'execute': {'send_task': 'send_task'},
    'log': {'get_default_logger': 'log.get_default_logger',
            'setup_logger': 'log.setup_logger',
            'setup_logging_subsystem': 'log.setup_logging_subsystem',
            'redirect_stdouts_to_logger': 'log.redirect_stdouts_to_logger'},
    'messaging': {'TaskConsumer': 'amqp.TaskConsumer',
                  'establish_connection': 'connection',
                  'get_consumer_set': 'amqp.TaskConsumer'},
    'registry': {'tasks': 'tasks'},
}}
COMPAT_LOCAL_SHA256 = 'f22cbb088bd0459330e3de7c2744a3307715c16ec021b91a229073b5d4b9c224'
COMPAT_PARENT_SHA256 = 'b4237322f6ed8e069919d82d32130517079843c4e20d6cd5e8bd4cefcae38c61'
COMPAT_FACTORIES = ('create_module', 'recreate_module', 'get_compat_module', 'getappattr')
COMPAT_HELPERS = ('get_origins', '_default_cls_attr')


def module_namespace(module):
    check(isinstance(module, ModuleType), 'target is not a module')
    # Bypass added __getattribute__/__dict__ descriptors; never resolve a native export.
    return ModuleType.__dict__['__dict__'].__get__(module, ModuleType)


def ast_code_bindings(tree, compiled):
    """Bind unique compiled definitions to their exact AST symbol and first line."""
    result = {}

    def visit(node, code, prefix=''):
        for definition in node.body:
            if not isinstance(definition, (ast.ClassDef, ast.FunctionDef)):
                continue
            qualname = prefix + definition.name
            candidates = [c for c in code.co_consts if type(c) is CodeType and c.co_name == definition.name]
            check(len(candidates) == 1 and qualname not in result, 'ambiguous native AST definition: ' + qualname)
            bound = candidates[0]
            firstline = definition.lineno
            if isinstance(definition, ast.FunctionDef):
                firstline = min([firstline] + [d.lineno for d in definition.decorator_list])
            check(bound.co_qualname == qualname and bound.co_firstlineno == firstline,
                  'compiled native AST identity mismatch: ' + qualname)
            result[qualname] = bound
            visit(definition, bound, qualname + ('.' if isinstance(definition, ast.ClassDef) else '.<locals>.'))

    visit(tree, compiled)
    return result


def compat_source_contract(source):
    """Parse and compile sealed bytes for comparison only. Never execute the code."""
    check(sha256(source) == COMPAT_LOCAL_SHA256, 'wrong frozen compatibility source')
    text = Path(source).read_text(encoding='utf-8')
    tree = ast.parse(text, filename=source)
    nodes = [n.value for n in tree.body if isinstance(n, ast.Assign) and
             any(isinstance(t, ast.Name) and t.id == 'COMPAT_MODULES' for t in n.targets)]
    check(len(nodes) == 1 and ast.literal_eval(nodes[0]) == R94_COMPAT_MODULES,
          'unexpected native COMPAT_MODULES AST')
    compiled = compile(text, source, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    codes = ast_code_bindings(tree, compiled)
    return ast.literal_eval(nodes[0]), codes


def parent_class_contract(source):
    """Static class attributes passed by the sealed celery.__init__ recreation call."""
    check(sha256(source) == COMPAT_PARENT_SHA256, 'wrong frozen parent recreation source')
    tree = ast.parse(Path(source).read_text(encoding='utf-8'), filename=source)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
             isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and
             n.func.value.id == 'local' and n.func.attr == 'recreate_module']
    check(len(calls) == 1 and len(calls[0].args) == 1 and isinstance(calls[0].args[0], ast.Name) and
          calls[0].args[0].id == '__name__', 'unexpected parent factory AST call')
    keywords = {k.arg: k.value for k in calls[0].keywords}
    check(None not in keywords and len(keywords) == len(calls[0].keywords), 'ambiguous parent factory keywords')
    by_module = ast.literal_eval(keywords.pop('by_module'))
    origins = {attr: module for module, attrs in by_module.items() for attr in attrs}
    exports = set(R94_COMPAT_MODULES['celery']) | set(origins) | set(keywords)
    return {'_all_by_module': by_module, '_direct': {}, '_object_origins': origins,
            '__all__': tuple(sorted(exports))}


def verify_generated_class(module, short, lazy, extra_keys=()):
    cls = type(module)
    check(type(cls) is type and cls.__bases__ == (lazy,), 'wrong generated module base/metaclass')
    data = vars(cls)
    check(set(data) == {'__module__', '__doc__'} | set(extra_keys) and
          type(data['__module__']) is str and data['__module__'] == '' and data['__doc__'] is None and
          cls.__name__ == short and cls.__qualname__ == short,
          'wrong generated module class shape or lookup/descriptor additions')
    return data


def verify_function_origin(function, code, namespace, source, qualname):
    check(inspect.isfunction(function) and function.__globals__ is namespace and
          function.__module__ == 'celery.local' and function.__qualname__ == qualname and
          function.__name__ == qualname.rsplit('.', 1)[-1] and
          function.__closure__ is None and function.__kwdefaults__ is None,
          'compatibility function binding mismatch: ' + qualname)
    check(str(Path(function.__code__.co_filename).resolve()) == source and
          function.__code__.co_firstlineno == code.co_firstlineno and function.__code__ == code,
          'compatibility function code origin mismatch: ' + qualname)


def verify_runtime_declarations(actual, declared):
    check(type(actual) is dict and list(actual) == ['celery'] and
          type(actual['celery']) is dict and list(actual['celery']) == list(declared['celery']),
          'runtime compatibility module set differs from AST')
    for short, attrs in declared['celery'].items():
        value = actual['celery'][short]
        check(type(value) is dict and list(value) == list(attrs) + ['__all__'],
              'runtime compatibility exports differ from AST: ' + short)
        check(type(value['__all__']) is list and all(type(x) is str for x in value['__all__']) and
              value['__all__'] == list(attrs), 'wrong native compatibility __all__: ' + short)
        check(all(type(value[k]) is str and value[k] == v for k, v in attrs.items()),
              'runtime compatibility target changed: ' + short)


def verify_factory_context(local, parent, source, spec, codes, declared):
    namespace = module_namespace(local)
    check(type(local) is ModuleType and namespace.get('__name__') == 'celery.local' and
          sys.modules.get('celery.local') is local, 'wrong native local module identity')
    check(namespace.get('sys') is sys and namespace.get('ModuleType') is ModuleType,
          'native compatibility factory globals changed')
    lazy, proxy = namespace.get('LazyModule'), namespace.get('Proxy')
    check(type(lazy) is type and lazy.__bases__ == (ModuleType,) and
          vars(lazy).get('__module__') == 'celery.local', 'wrong native LazyModule base/origin')
    check(set(vars(lazy)) == {'__module__', '__doc__', '_compat_modules', '_all_by_module', '_direct',
                              '_object_origins', '__getattr__', '__dir__', '__reduce__'},
          'native LazyModule has extra/missing lookup or descriptor attributes')
    check(type(proxy) is type and proxy.__bases__ == (object,) and
          vars(proxy).get('__slots__') == ('__local', '__args', '__kwargs', '__dict__'),
          'wrong native Proxy class/slots')
    check('__getattribute__' not in vars(proxy) and
          inspect.getattr_static(proxy, '__getattribute__') is object.__getattribute__,
          'native Proxy must inherit the unchanged object attribute lookup')
    for slot in ('_Proxy__local', '_Proxy__args', '_Proxy__kwargs'):
        descriptor = vars(proxy).get(slot)
        check(type(descriptor) is MemberDescriptorType and descriptor.__objclass__ is proxy,
              'native Proxy raw slot replaced')
    for symbol in COMPAT_FACTORIES + COMPAT_HELPERS:
        verify_function_origin(namespace.get(symbol), codes[symbol], namespace, source, symbol)
    defaults = {'create_module': (None, None, lazy, None),
                'recreate_module': (None, None, None, lazy),
                'get_compat_module': None, 'getappattr': None,
                'get_origins': None, '_default_cls_attr': None}
    for symbol, expected in defaults.items():
        check(namespace[symbol].__defaults__ == expected, 'native factory defaults changed: ' + symbol)
    for cls, methods in ((lazy, ('__getattr__', '__dir__', '__reduce__')),
                         (proxy, ('__init__', '_get_current_object', '__call__', '__getattr__'))):
        for method in methods:
            qualname = ('LazyModule' if cls is lazy else 'Proxy') + '.' + method
            if cls is proxy:
                check(type(vars(cls).get(method)) is FunctionType, 'native Proxy method is not a plain function: ' + method)
            verify_function_origin(vars(cls).get(method), codes[qualname], namespace, source, qualname)
            if cls is proxy and method != '__init__':
                check(vars(cls)[method].__defaults__ is None, 'native Proxy method defaults changed: ' + method)
    check(vars(proxy)['__init__'].__defaults__ == (None, None, None, None),
          'native Proxy constructor defaults changed')
    for key, expected in (('_compat_modules', ()), ('_all_by_module', {}),
                          ('_direct', {}), ('_object_origins', {})):
        check(type(vars(lazy).get(key)) is type(expected) and vars(lazy)[key] == expected,
              'native LazyModule defaults changed: ' + key)
    verify_runtime_declarations(namespace.get('COMPAT_MODULES'), declared)
    check(isinstance(parent, ModuleType) and sys.modules.get('celery') is parent,
          'wrong native generated parent identity')
    parent_data = module_namespace(parent)
    parent_source = str((Path(spec['source_root']) / 'celery' / '__init__.py').resolve())
    check(parent_data.get('__file__') is not None and
          str(Path(parent_data['__file__']).resolve()) == parent_source and
          spec['source_files'].get(parent_source) == COMPAT_PARENT_SHA256 == sha256(parent_source),
          'unsealed native parent recreation source')
    expected = parent_class_contract(parent_source)
    parent_cls = verify_generated_class(parent, 'celery', lazy, set(expected) | {'_compat_modules'})
    check(parent_data.get('__name__') == 'celery' and parent_data.get('local') is local and
          parent_cls['_compat_modules'] is namespace['COMPAT_MODULES']['celery'],
          'wrong native generated parent bindings')
    for key, value in expected.items():
        observed = parent_cls[key]
        if key == '__all__':
            check(type(observed) is tuple and all(type(x) is str for x in observed) and
                  len(observed) == len(value) and set(observed) == set(value), 'wrong native parent export set')
        else:
            check(type(observed) is dict and observed == value, 'wrong native parent class declaration: ' + key)
    return lazy, proxy


def verify_virtual_shape(name, module, local, parent, declared):
    short = name.removeprefix('celery.')
    check(name == 'celery.' + short and short in declared['celery'],
          'undeclared fileless target module: ' + name)
    lazy, proxy = module_namespace(local)['LazyModule'], module_namespace(local)['Proxy']
    verify_generated_class(module, short, lazy)
    check(sys.modules.get(name) is module and module_namespace(parent).get(short) is module,
          'generated module registry/parent identity differs')
    data, attrs = module_namespace(module), declared['celery'][short]
    check(set(data) == set(attrs) | {'__name__', '__doc__', '__package__', '__loader__', '__spec__', '__all__'},
          'missing/additional generated module attributes')
    check(data['__name__'] == short and all(data[k] is None for k in
          ('__doc__', '__package__', '__loader__', '__spec__')), 'wrong generated module metadata')
    check(type(data['__all__']) is list and all(type(x) is str for x in data['__all__']) and
          data['__all__'] == list(attrs), 'wrong generated module exports')
    for attr, target in attrs.items():
        value = data[attr]
        check(type(value) is proxy, 'wrong native proxy class: ' + attr)
        # Bind verified plain Python methods only; do not call a Proxy or its resolver.
        for method in ('__call__', '_get_current_object'):
            bound = object.__getattribute__(value, method)
            check(type(bound) is MethodType and bound.__self__ is value and
                  bound.__func__ is vars(proxy)[method], 'native Proxy instance callable shadowed: ' + attr + '.' + method)
        # Do not read Proxy.__dict__/__class__ or resolve a proxy/current_app.
        local_value = object.__getattribute__(value, '_Proxy__local')
        args = object.__getattribute__(value, '_Proxy__args')
        kwargs = object.__getattribute__(value, '_Proxy__kwargs')
        check(local_value is module_namespace(local)['getappattr'] and type(args) is tuple and len(args) == 1 and
              type(args[0]) is str and args[0] == target and type(kwargs) is dict and not kwargs,
              'wrong native proxy raw binding: ' + attr)
    return True


def verify_native_generated_module(name, module, spec):
    """No fileless exemption: only the four exact sealed r94 native declarations."""
    try:
        check(type(spec['original_rank']) is int and spec['original_rank'] == 94 and
              name in {'celery.' + n for n in R94_COMPAT_MODULES['celery']},
              'undeclared fileless target module: ' + name)
        source = str((Path(spec['source_root']) / 'celery' / 'local.py').resolve())
        local, parent = sys.modules.get('celery.local'), sys.modules.get('celery')
        check(type(local) is ModuleType and module_namespace(local).get('__file__') is not None and
              str(Path(module_namespace(local)['__file__']).resolve()) == source and
              spec['source_files'].get(source) == COMPAT_LOCAL_SHA256 == sha256(source),
              'unsealed compatibility factory source')
        declared, codes = compat_source_contract(source)
        verify_factory_context(local, parent, source, spec, codes, declared)
        verify_virtual_shape(name, module, local, parent, declared)
        return dict(kind='NATIVE_GENERATED_COMPAT_MODULE', declaration_source=source,
                    declaration_sha256=COMPAT_LOCAL_SHA256, parent_source_sha256=COMPAT_PARENT_SHA256,
                    factories={k: {'qualname': k, 'firstlineno': codes[k].co_firstlineno,
                                   'source_file': source, 'module': 'celery.local'} for k in COMPAT_FACTORIES},
                    helpers={k: {'qualname': k, 'firstlineno': codes[k].co_firstlineno,
                                 'source_file': source, 'module': 'celery.local'} for k in COMPAT_HELPERS},
                    generated_class_keys=sorted(vars(type(module))),
                    generated_parent_class_keys=sorted(vars(type(parent))),
                    exports=list(declared['celery'][name.split('.')[1]]), proxy_resolution_performed=False)
    except IdentityFailure:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OSError, SyntaxError) as exc:
        raise IdentityFailure('invalid native compatibility provenance: ' + str(exc)) from exc
