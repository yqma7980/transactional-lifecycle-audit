"""Author synthetic QA only: no target import, source execution, or pilot."""
import argparse
import copy
import importlib.abc
import json
import platform
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = ROOT.parent / 'M-2026-003_S10_G2G3_RECOVERY_20260907_052246'
SOURCE = PRIOR / 'sources/r094/git_transport/acquisition_001'
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
ATTEMPTED_IMPORTS = []
ATTEMPTED_TARGET_CALLS = []
DENIED = {'celery', 'django', 'kombu', 'amqp', 'vine', 'billiard', 'click',
          'click_didyoumean', 'click_repl', 'click_plugins', 'dateutil', 'six',
          'prompt_toolkit', 'wcwidth', 'colorama', 'tzdata', 's10_native_recipe'}


class NoTarget(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in DENIED:
            ATTEMPTED_IMPORTS.append(fullname)
            raise AssertionError('No target imports in synthetic QA: ' + fullname)


sys.meta_path.insert(0, NoTarget())
import identity
import test_synthetic as original

# Only synthetic harness locations change; all 14 original test bodies stay identical.
original.SCOPE = HERE
original.SOURCE_BASE = SOURCE


def no_target_calls(frame, event, arg):
    if event == 'call' and (str(SOURCE) in frame.f_code.co_filename or
                            frame.f_code.co_filename == str(original.RECIPE_PATH)):
        ATTEMPTED_TARGET_CALLS.append(frame.f_code.co_name)
        raise AssertionError('A dormant source code object was called')


@contextmanager
def inert_modules(side='after'):
    """Stand-ins only. Compiled native code is attached for comparison, never called."""
    source_root = SOURCE / side / 'tree'
    source = str(source_root / 'celery/local.py')
    declared, codes = identity.compat_source_contract(source)
    local = ModuleType('celery.local')
    namespace = vars(local)
    namespace.update(__file__=source, sys=sys, ModuleType=ModuleType)
    lazy = type('LazyModule', (ModuleType,), {'__module__': 'celery.local',
        '_compat_modules': (), '_all_by_module': {}, '_direct': {}, '_object_origins': {}})
    proxy = type('Proxy', (object,), {'__module__': 'celery.local',
        '__slots__': ('__local', '__args', '__kwargs', '__dict__')})
    namespace.update(LazyModule=lazy, Proxy=proxy)
    defaults = {'create_module': (None, None, lazy, None),
                'recreate_module': (None, None, None, lazy),
                'get_compat_module': None, 'getappattr': None,
                'get_origins': None, '_default_cls_attr': None}
    for symbol in identity.COMPAT_FACTORIES + identity.COMPAT_HELPERS:
        namespace[symbol] = FunctionType(codes[symbol], namespace, symbol, defaults[symbol])
    for cls, methods in ((lazy, ('__getattr__', '__dir__', '__reduce__')),
                         (proxy, ('__init__', '_get_current_object', '__call__', '__getattr__'))):
        for method in methods:
            qualname = cls.__name__ + '.' + method
            default = (None, None, None, None) if qualname == 'Proxy.__init__' else None
            setattr(cls, method, FunctionType(codes[qualname], namespace, method, default))
    actual = copy.deepcopy(declared)
    for attrs in actual['celery'].values():
        attrs['__all__'] = list(attrs)
    namespace['COMPAT_MODULES'] = actual
    parent_attrs = identity.parent_class_contract(str(source_root / 'celery/__init__.py'))
    parent_cls = type('celery', (lazy,), dict(parent_attrs, __module__='', _compat_modules=actual['celery']))
    parent = parent_cls('celery')
    vars(parent).update(__file__=str(source_root / 'celery/__init__.py'), local=local)
    modules = {'celery': parent, 'celery.local': local}
    for short, attrs in declared['celery'].items():
        module = type(short, (lazy,), {'__module__': ''})(short)
        for name, target in attrs.items():
            value = object.__new__(proxy)
            object.__setattr__(value, '_Proxy__local', namespace['getappattr'])
            object.__setattr__(value, '_Proxy__args', (target,))
            object.__setattr__(value, '_Proxy__kwargs', {})
            vars(module)[name] = value
        vars(module)['__all__'] = list(attrs)
        vars(parent)[short] = module
        modules['celery.' + short] = module
    spec = dict(original_rank=94, source_root=str(source_root), code_bindings={},
                source_files={source: identity.sha256(source),
                    str(source_root / 'celery/__init__.py'): identity.sha256(source_root / 'celery/__init__.py')})
    with patch.dict(sys.modules, modules):
        yield spec, modules, declared, codes


class ProvenanceTests(unittest.TestCase):
    def test_exact_ast_and_hashes_both_sides(self):
        for side in ('before', 'after'):
            source = str(SOURCE / side / 'tree/celery/local.py')
            declared, codes = identity.compat_source_contract(source)
            self.assertEqual(declared, identity.R94_COMPAT_MODULES)
            self.assertEqual(list(declared['celery']), ['execute', 'log', 'messaging', 'registry'])
            self.assertTrue(all(type(codes[n]) is CodeType for n in identity.COMPAT_FACTORIES))
            self.assertEqual(identity.sha256(source), identity.COMPAT_LOCAL_SHA256)
            self.assertEqual(identity.sha256(SOURCE / side / 'tree/celery/__init__.py'),
                             identity.COMPAT_PARENT_SHA256)

    def test_all_four_inert_module_shapes_both_sides(self):
        for side in ('before', 'after'):
            with inert_modules(side) as (spec, modules, declared, codes):
                value = identity.verify_loaded_targets(spec)
                self.assertEqual(len(value), 6)
                for short, attrs in declared['celery'].items():
                    proof = value['celery.' + short]
                    self.assertEqual(proof['kind'], 'NATIVE_GENERATED_COMPAT_MODULE')
                    self.assertEqual(proof['exports'], list(attrs))
                    self.assertFalse(proof['proxy_resolution_performed'])

    def test_wrong_factory_code_and_globals_rejected(self):
        for symbol in identity.COMPAT_FACTORIES:
            with inert_modules() as (spec, modules, declared, codes):
                local = modules['celery.local']
                original_function = vars(local)[symbol]
                source = str(Path(spec['source_root']) / 'celery/local.py')
                toy = compile('def stand_in():\n    return None\n', source, 'exec').co_consts[0]
                toy = toy.replace(co_name=symbol, co_qualname=symbol,
                                  co_firstlineno=codes[symbol].co_firstlineno)
                vars(local)[symbol] = FunctionType(toy, vars(local), symbol, original_function.__defaults__)
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)
                vars(local)[symbol] = FunctionType(codes[symbol], dict(vars(local)), symbol,
                                                  original_function.__defaults__)
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)

    def test_factory_defaults_and_class_origins_rejected(self):
        mutations = [lambda m: setattr(m['celery.local'].create_module, '__defaults__', (None, None, ModuleType, None)),
            lambda m: setattr(m['celery.local'].LazyModule, '__dir__', lambda self: []),
            lambda m: setattr(m['celery.local'].Proxy, '_get_current_object', lambda self: None),
            lambda m: setattr(m['celery.local'].LazyModule, '_direct', {'unexpected': 'module'}),
            lambda m: setattr(m['celery.local'].Proxy, '_Proxy__local', None)]
        for mutate in mutations:
            with inert_modules() as (spec, modules, declared, codes):
                mutate(modules)
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)

    def test_wrong_proxy_class_and_raw_bindings_rejected(self):
        for slot, bad in [('_Proxy__local', object()), ('_Proxy__args', ['send_task']),
                          ('_Proxy__args', ('tasks',)), ('_Proxy__args', (True,)),
                          ('_Proxy__kwargs', {'ignored': True}), ('_Proxy__kwargs', None)]:
            with inert_modules() as (spec, modules, declared, codes):
                value = vars(modules['celery.execute'])['send_task']
                object.__setattr__(value, slot, bad)
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)
        with inert_modules() as (spec, modules, declared, codes):
            vars(modules['celery.execute'])['send_task'] = object()
            with self.assertRaises(identity.IdentityFailure):
                identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)

    def test_parent_and_registry_identities_rejected(self):
        mutations = [lambda m: vars(m['celery']).update(execute=object()),
            lambda m: sys.modules.update({'celery': ModuleType('celery')}),
            lambda m: sys.modules.update({'celery.execute': ModuleType('execute')}),
            lambda m: vars(m['celery']).update(local=ModuleType('celery.local')),
            lambda m: setattr(type(m['celery']), '_compat_modules', copy.deepcopy(identity.R94_COMPAT_MODULES['celery'])),
            lambda m: vars(m['celery']).update(__file__=__file__)]
        for mutate in mutations:
            with inert_modules() as (spec, modules, declared, codes):
                mutate(modules)
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)

    def test_unexpected_missing_module_and_exports_rejected(self):
        with inert_modules() as (spec, modules, declared, codes):
            sys.modules['celery.unexpected'] = ModuleType('unexpected')
            with self.assertRaises(identity.IdentityFailure):
                identity.verify_loaded_targets(spec)
        with inert_modules() as (spec, modules, declared, codes):
            del sys.modules['celery.log']
            with self.assertRaises(identity.IdentityFailure):
                identity.verify_loaded_targets(spec)
        for key, bad in [('unexpected', None), ('__file__', None), ('__loader__', object()),
                         ('__all__', ('send_task',)), ('__all__', ['other']), ('__name__', 'celery.execute')]:
            with inert_modules() as (spec, modules, declared, codes):
                vars(modules['celery.execute'])[key] = bad
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)

    def test_changed_runtime_declaration_and_origin_rejected(self):
        with inert_modules() as (spec, modules, declared, codes):
            modules['celery.local'].COMPAT_MODULES['celery']['execute']['send_task'] = 'tasks'
            with self.assertRaises(identity.IdentityFailure):
                identity.verify_loaded_targets(spec)
        with inert_modules() as (spec, modules, declared, codes):
            modules['celery.local'].__file__ = __file__
            with self.assertRaises(identity.IdentityFailure):
                identity.verify_loaded_targets(spec)
        with inert_modules() as (spec, modules, declared, codes):
            spec['source_files'][str(Path(spec['source_root']) / 'celery/local.py')] = '0' * 64
            with self.assertRaises(identity.IdentityFailure):
                identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)

    def test_scientific_components_are_byte_identical(self):
        for name in ('observations.py', 'evaluator.py', 'spec_builder.py', 'test_synthetic.py'):
            self.assertEqual(identity.sha256(HERE / name),
                             identity.sha256(PRIOR / 'protocols/celery_recovery/r094_native' / name))
        self.assertEqual(identity.PRIOR_SOURCE_ROOT, PRIOR)
        self.assertEqual(identity.RECOVERY_ROOT, ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    report = Path(args.report).resolve()
    if HERE not in report.parents:
        raise ValueError('QA artifacts must remain in owned adapter directory')
    if platform.python_version() != '3.12.10' or not sys.flags.isolated or not sys.flags.no_site:
        raise ValueError('Use actual host CPython 3.12.10 with -I -S -B')
    before = {str(p): identity.sha256(p) for p in HERE.glob('*.py')}
    old_paths = list((PRIOR / 'protocols/celery_recovery/r094_native').glob('*.py'))
    old_paths += [PRIOR / 'protocols/celery_recovery/r080_native_v3/identity.py',
                  original.PROTOCOL_PATH, original.RECIPE_PATH,
                  PRIOR / 'protocols/celery_recovery/R094_PREP_PLAN.json']
    old_paths += [SOURCE / side / 'tree' / relative for side in ('before', 'after')
                  for relative in ('celery/local.py', 'celery/__init__.py')]
    baseline = {str(p): identity.sha256(p) for p in old_paths}
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(original.Tests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(ProvenanceTests)])
    prior_profile = sys.getprofile()
    sys.setprofile(no_target_calls)
    try:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        sys.setprofile(prior_profile)
    drift = [p for p, h in baseline.items() if identity.sha256(p) != h]
    adapter_drift = [p for p, h in before.items() if identity.sha256(p) != h]
    passed = result.wasSuccessful() and not drift and not adapter_drift and not ATTEMPTED_IMPORTS and not ATTEMPTED_TARGET_CALLS
    payload = dict(schema='AUTHOR_SYNTHETIC_QA_NOT_NATIVE_NOT_INDEPENDENT', passed=passed,
        python=platform.python_version(), executable=sys.executable, tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors),
        original_test_bodies_byte_identical=True, original_test_path_overrides=['SCOPE', 'SOURCE_BASE'],
        source_code_compiled_not_executed=True, synthetic_inert_objects_only=True,
        attempted_target_imports=ATTEMPTED_IMPORTS, attempted_target_calls=ATTEMPTED_TARGET_CALLS,
        network_calls=0, native_operations=0, adapter_file_hashes=before,
        adapter_file_drift=adapter_drift, old_input_hashes=baseline, old_input_drift=drift,
        failure_details=[text for _, text in result.failures + result.errors])
    with report.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: payload[k] for k in ('passed', 'tests_run', 'failures', 'errors')}))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
