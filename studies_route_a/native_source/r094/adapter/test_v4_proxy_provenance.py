"""AUTHOR_NOT_NONAUTHOR: bounded synthetic repair QA; no native Proxy calls."""
import argparse
import json
import platform
import sys
import unittest
from pathlib import Path
from types import FunctionType, MethodType

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import test_v3_regressions as previous
import test_virtual_provenance as base
import identity

V3 = HERE.with_name('r094_native_v3')
PARENT = base.ROOT.parent / 'M-2026-003_S10_R094_G3_20260907_163900'
SYNTHETIC_CALLS = []


def replacement(*args, **kwargs):
    SYNTHETIC_CALLS.append('uncalled synthetic replacement was executed')
    raise AssertionError('No Proxy or replacement calls are allowed in this QA')


class ProxyCallTests(unittest.TestCase):
    def assert_rejected(self, spec, modules):
        with self.assertRaises(identity.IdentityFailure):
            identity.verify_native_generated_module('celery.execute', modules['celery.execute'], spec)
        with self.assertRaises(identity.IdentityFailure):
            identity.verify_loaded_targets(spec)

    def test_exact_uncalled_call_chain_both_sources_all_exports(self):
        for side in ('before', 'after'):
            with base.inert_modules(side) as (spec, modules, declared, codes):
                proxy_cls = modules['celery.local'].Proxy
                self.assertNotIn('__getattribute__', vars(proxy_cls))
                self.assertIs(proxy_cls.__getattribute__, object.__getattribute__)
                for method in ('__call__', '__getattr__', '_get_current_object'):
                    self.assertEqual(vars(proxy_cls)[method].__code__, codes['Proxy.' + method])
                for short, attrs in declared['celery'].items():
                    for attr in attrs:
                        value = identity.module_namespace(modules['celery.' + short])[attr]
                        for method in ('__call__', '_get_current_object'):
                            bound = object.__getattribute__(value, method)
                            self.assertIs(type(bound), MethodType)
                            self.assertIs(bound.__func__, vars(proxy_cls)[method])
                            self.assertIs(bound.__self__, value)
                self.assertEqual(len(identity.verify_loaded_targets(spec)), 6)

    def test_proxy_class_call_override_reviewer_regression(self):
        for side in ('before', 'after'):
            with base.inert_modules(side) as (spec, modules, declared, codes):
                proxy_cls = modules['celery.local'].Proxy
                self.assertEqual(vars(proxy_cls)['__call__'].__code__, codes['Proxy.__call__'])
                proxy_cls.__call__ = replacement
                self.assert_rejected(spec, modules)
        self.assertEqual(SYNTHETIC_CALLS, [])

    def test_same_file_call_and_lookup_symbol_swaps_rejected(self):
        for method in ('__call__', '__getattr__'):
            with base.inert_modules() as (spec, modules, declared, codes):
                proxy_cls = modules['celery.local'].Proxy
                original = vars(proxy_cls)[method]
                other = vars(proxy_cls)['_get_current_object']
                self.assertEqual(original.__code__.co_filename, other.__code__.co_filename)
                setattr(proxy_cls, method, other)
                self.assert_rejected(spec, modules)

    def test_same_metadata_different_call_code_rejected(self):
        with base.inert_modules() as (spec, modules, declared, codes):
            namespace = identity.module_namespace(modules['celery.local'])
            expected = codes['Proxy.__call__']
            forged = replacement.__code__.replace(co_filename=expected.co_filename,
                co_name='__call__', co_qualname='Proxy.__call__', co_firstlineno=expected.co_firstlineno)
            function = FunctionType(forged, namespace, '__call__')
            self.assertEqual(function.__module__, 'celery.local')
            self.assertEqual(function.__qualname__, 'Proxy.__call__')
            namespace['Proxy'].__call__ = function
            self.assert_rejected(spec, modules)

    def test_missing_wrapped_and_descriptor_call_methods_rejected_without_execution(self):
        for kind in ('missing', 'none', 'staticmethod', 'classmethod', 'property'):
            with self.subTest(kind=kind), base.inert_modules() as (spec, modules, declared, codes):
                cls = modules['celery.local'].Proxy
                original = vars(cls)['__call__']
                if kind == 'missing':
                    delattr(cls, '__call__')
                else:
                    value = {'none': None, 'staticmethod': staticmethod(original),
                             'classmethod': classmethod(original), 'property': property(replacement)}[kind]
                    setattr(cls, '__call__', value)
                self.assert_rejected(spec, modules)
        self.assertEqual(SYNTHETIC_CALLS, [])

    def test_inherited_object_lookup_cannot_be_replaced_or_shadowed(self):
        for lookup in (replacement, object.__getattribute__, property(replacement)):
            with base.inert_modules() as (spec, modules, declared, codes):
                modules['celery.local'].Proxy.__getattribute__ = lookup
                self.assert_rejected(spec, modules)
        self.assertEqual(SYNTHETIC_CALLS, [])

    def test_instance_callable_shadow_and_wrong_bound_receiver_rejected(self):
        for method in ('__call__', '_get_current_object'):
            for kind in ('plain_function', 'wrong_function', 'wrong_receiver'):
                with self.subTest(method=method, kind=kind), base.inert_modules() as (spec, modules, declared, codes):
                    cls = modules['celery.local'].Proxy
                    value = identity.module_namespace(modules['celery.execute'])['send_task']
                    bad = replacement
                    if kind == 'wrong_function':
                        bad = MethodType(replacement, value)
                    elif kind == 'wrong_receiver':
                        bad = MethodType(vars(cls)[method], object.__new__(cls))
                    object.__setattr__(value, method, bad)
                    self.assert_rejected(spec, modules)
        self.assertEqual(SYNTHETIC_CALLS, [])

    def test_call_chain_defaults_are_exact(self):
        for method in ('__call__', '__getattr__', '_get_current_object'):
            with base.inert_modules() as (spec, modules, declared, codes):
                function = vars(modules['celery.local'].Proxy)[method]
                self.assertIsNone(function.__defaults__)
                function.__defaults__ = (None,)
                self.assert_rejected(spec, modules)

    def test_science_and_driver_delta_are_byte_exact(self):
        for name in ('evaluator.py', 'observations.py', 'spec_builder.py', 'test_synthetic.py'):
            self.assertEqual(identity.sha256(HERE / name), identity.sha256(V3 / name))
        self.assertEqual((HERE / 'driver.py').read_bytes(), (V3 / 'driver.py').read_bytes().replace(
            b'celery_completion_r094_v3', b'celery_completion_r094_v4'))
        self.assertEqual(identity.RECOVERY_ROOT, base.ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    report = Path(args.report).resolve()
    if HERE not in report.parents or platform.python_version() != '3.12.10':
        raise ValueError('Report must be in v4; use actual Python3.12.10')
    if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
        raise ValueError('Use -I -S -B')
    adapter_hashes = {str(p): identity.sha256(p) for p in HERE.glob('*.py')}
    preserved = [p for p in V3.rglob('*') if p.is_file()]
    preserved += [PARENT / 'governance/PROVENANCE_REPAIR_SCOPE_01.json']
    preserved += [PARENT / 'reviews' / name for name in (
        'NONAUTHOR_R94_V3_REVIEW.json', 'NONAUTHOR_R94_V3_REVIEW.md',
        'test_virtual_provenance_independent.py', 'test_proxy_call_confirmation.py',
        'qa_adapter_v3_01/work/PROVENANCE_QA.json', 'qa_proxy_confirmation_01/work/PROXY_CALL_QA.json',
        'qa_scientific_v3_01/work/SCIENTIFIC_QA.json')]
    preserved += [base.PRIOR / 'governance/frozen_protocols/r094' / name
                  for name in ('CASE_PILOT_PROTOCOL.json', 'runnable_core_recipe.py')]
    preserved += [base.SOURCE / side / 'tree' / name for side in ('before', 'after')
                  for name in ('celery/local.py', 'celery/__init__.py')]
    preserved += [base.ROOT / 'harness' / name for name in ('run_r94_pilot_v3.py',
                  'smoke_gate_v2.py', 'collector_v5.py', 'bounded_runner_v4.py')]
    input_hashes = {str(p): identity.sha256(p) for p in preserved}
    authority_path = PARENT / 'reviews/NONAUTHOR_R94_V3_REVIEW.json'
    authority = json.loads(authority_path.read_text(encoding='utf-8'))
    if authority['passed'] is not False or authority['open_acceptance_blockers'] != 1:
        raise ValueError('Expected the preserved failed v3 review with one blocker')
    suites = [base.original.Tests, base.ProvenanceTests, previous.ReviewerRegressionTests, ProxyCallTests]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in suites)
    old_profile = sys.getprofile()
    sys.setprofile(base.no_target_calls)
    try:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        sys.setprofile(old_profile)
    input_drift = [p for p, digest in input_hashes.items() if identity.sha256(p) != digest]
    adapter_drift = [p for p, digest in adapter_hashes.items() if identity.sha256(p) != digest]
    v3_members = {str(p) for p in V3.rglob('*') if p.is_file()}
    v3_before = {p for p in input_hashes if Path(p).is_relative_to(V3)}
    imports = base.ATTEMPTED_IMPORTS + base.original.ATTEMPTED_IMPORTS
    descriptor_calls = SYNTHETIC_CALLS + previous.CALLS
    passed = result.wasSuccessful() and not input_drift and not adapter_drift and v3_members == v3_before
    passed = passed and not imports and not base.ATTEMPTED_TARGET_CALLS and not descriptor_calls
    payload = dict(schema='AUTHOR_SYNTHETIC_QA_NOT_NATIVE_NOT_INDEPENDENT', author_status='AUTHOR_NOT_NONAUTHOR',
        passed=passed, python=platform.python_version(), executable=sys.executable, tests_run=result.testsRun,
        errors=len(result.errors), failures=len(result.failures), native_operations=0, network_calls=0,
        attempted_target_imports=imports, attempted_target_calls=base.ATTEMPTED_TARGET_CALLS,
        adapter_file_hashes=adapter_hashes, adapter_file_drift=adapter_drift,
        preserved_input_hashes=input_hashes, preserved_input_drift=input_drift,
        v3_membership_unchanged=v3_members == v3_before,
        provenance_detail=dict(schema='R094_V4_PROXY_CALL_AUTHOR_PROVENANCE_QA_1',
            inherited_scientific_tests=14, inherited_provenance_tests=18, proxy_call_tests=9,
            repair_authority=str(authority_path), repair_authority_sha256=input_hashes[str(authority_path)],
            confirmed_blocker='R94-V3-PROXY-CALL-BINDING', prior_independent_results=authority['tests'],
            prior_independent_tests_not_rerun_or_claimed_as_author_tests=True,
            unexpected_synthetic_callable_or_descriptor_calls=descriptor_calls,
            synthetic_boundary='Inert modules/classes/proxies and uncalled compiled source code objects only. No native import, source execution, factory call, Proxy call or frozen recipe execution. Methods are bound and compared, never invoked.',
            independent_review_claimed=False, source_or_recipe_patched=False, native_cells_launched=0),
        failure_details=[text for _, text in result.failures + result.errors])
    with report.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: payload[k] for k in ('schema', 'passed', 'tests_run', 'failures', 'errors')}))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
