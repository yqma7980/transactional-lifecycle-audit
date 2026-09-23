"""Author synthetic adaptations of the r80 nonauthor provenance negatives; r94 only."""
import argparse
import ast
import json
import platform
import sys
import unittest
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import test_virtual_provenance as base
import identity

V2 = HERE.with_name('r094_native_v2')
REVIEW = base.ROOT / 'reviews/r80'
CALLS = []


class ReviewerRegressionTests(unittest.TestCase):
    def test_generated_class_override_changes_export(self):
        for short in identity.R94_COMPAT_MODULES['celery']:
            with base.inert_modules() as (spec, modules, declared, codes):
                module = modules['celery.' + short]
                attr = next(iter(declared['celery'][short]))

                def different_lookup(self, key):
                    if key == attr:
                        return 'SYNTHETIC_WRONG_EXPORTED_VALUE'
                    return ModuleType.__getattribute__(self, key)

                type(module).__getattribute__ = different_lookup
                self.assertEqual(getattr(module, attr), 'SYNTHETIC_WRONG_EXPORTED_VALUE')
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_native_generated_module('celery.' + short, module, spec)
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_loaded_targets(spec)

    def test_descriptors_and_fake_file_dictionary_cannot_bypass_class_shape(self):
        for key in ('send_task', '__dict__', '__doc__'):
            with base.inert_modules() as (spec, modules, declared, codes):
                module = modules['celery.execute']
                forged = dict(identity.module_namespace(module), __file__=str(Path(spec['source_root']) / 'celery/local.py'))

                def descriptor(self):
                    CALLS.append('synthetic descriptor should not be evaluated by verifier')
                    return forged

                if key == '__dict__':
                    cls = type(module)
                    replacement = type(cls.__name__, cls.__bases__, dict(vars(cls), __dict__=property(descriptor)))
                    ModuleType.__setattr__(module, '__class__', replacement)
                else:
                    setattr(type(module), key, property(descriptor))
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_loaded_targets(spec)
                self.assertEqual(CALLS, [])

    def test_parent_and_lazy_base_lookup_additions_rejected(self):
        for target in ('parent', 'base'):
            for key in ('__getattribute__', '__dict__', 'execute'):
                with base.inert_modules() as (spec, modules, declared, codes):
                    cls = type(modules['celery']) if target == 'parent' else modules['celery.local'].LazyModule

                    def foreign_lookup(self, *args):
                        CALLS.append('synthetic lookup should not be evaluated by verifier')
                        raise AssertionError('lookup must not run')

                    if key == '__dict__':
                        replacement = type(cls.__name__, cls.__bases__, dict(vars(cls), __dict__=property(foreign_lookup)))
                        if target == 'parent':
                            ModuleType.__setattr__(modules['celery'], '__class__', replacement)
                        else:
                            namespace = identity.module_namespace(modules['celery.local'])
                            namespace['LazyModule'] = replacement
                            namespace['create_module'].__defaults__ = (None, None, replacement, None)
                            namespace['recreate_module'].__defaults__ = (None, None, None, replacement)
                            for name, module in modules.items():
                                if name != 'celery.local':
                                    type(module).__bases__ = (replacement,)
                    else:
                        setattr(cls, key, foreign_lookup if key == '__getattribute__' else property(foreign_lookup))
                    with self.assertRaises(identity.IdentityFailure):
                        identity.verify_loaded_targets(spec)
                    self.assertEqual(CALLS, [])

    def test_generated_class_names_and_parent_declarations_rejected(self):
        for field, bad in [('__name__', 'other'), ('__qualname__', 'other'), ('__module__', 'celery.local')]:
            with base.inert_modules() as (spec, modules, declared, codes):
                setattr(type(modules['celery.execute']), field, bad)
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_loaded_targets(spec)
        for field, bad in [('_all_by_module', {}), ('_direct', {'extra': 'celery'}),
                           ('_object_origins', {}), ('__all__', ('execute',))]:
            with base.inert_modules() as (spec, modules, declared, codes):
                setattr(type(modules['celery']), field, bad)
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_loaded_targets(spec)

    def test_same_file_factory_helper_decorator_symbol_swap(self):
        for symbol in identity.COMPAT_FACTORIES + identity.COMPAT_HELPERS:
            with base.inert_modules() as (spec, modules, declared, codes):
                namespace = identity.module_namespace(modules['celery.local'])
                replacement = namespace['getappattr' if symbol != 'getappattr' else 'create_module']
                self.assertEqual(namespace[symbol].__code__.co_filename, replacement.__code__.co_filename)
                namespace[symbol] = replacement
                with self.assertRaises(identity.IdentityFailure):
                    identity.verify_loaded_targets(spec)

    def test_same_file_joint_resolver_substitution(self):
        with base.inert_modules() as (spec, modules, declared, codes):
            namespace = identity.module_namespace(modules['celery.local'])
            namespace['getappattr'] = namespace['get_origins']
            for short, attrs in declared['celery'].items():
                for attr in attrs:
                    proxy = identity.module_namespace(modules['celery.' + short])[attr]
                    object.__setattr__(proxy, '_Proxy__local', namespace['getappattr'])
            with self.assertRaises(identity.IdentityFailure):
                identity.verify_loaded_targets(spec)

    def test_exact_function_symbol_module_qualname_and_firstline(self):
        for symbol in identity.COMPAT_FACTORIES + identity.COMPAT_HELPERS:
            for field, bad in [('__name__', 'foreign'), ('__qualname__', 'foreign'),
                               ('__module__', 'foreign.module'), ('firstline', -1)]:
                with base.inert_modules() as (spec, modules, declared, codes):
                    function = identity.module_namespace(modules['celery.local'])[symbol]
                    if field == 'firstline':
                        function.__code__ = function.__code__.replace(co_firstlineno=function.__code__.co_firstlineno + 1)
                    else:
                        setattr(function, field, bad)
                    with self.assertRaises(identity.IdentityFailure):
                        identity.verify_loaded_targets(spec)

    def test_ast_definition_binding_and_no_r94_function_export(self):
        for side in ('before', 'after'):
            source = str(base.SOURCE / side / 'tree/celery/local.py')
            declared, codes = identity.compat_source_contract(source)
            tree = ast.parse(Path(source).read_text(encoding='utf-8'))
            functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
            for symbol in identity.COMPAT_FACTORIES + identity.COMPAT_HELPERS:
                self.assertEqual(codes[symbol].co_qualname, symbol)
                self.assertEqual(codes[symbol].co_firstlineno, functions[symbol].lineno)
            self.assertNotIn('decorators', declared['celery'])
            self.assertTrue(all(type(value) is str for attrs in declared['celery'].values() for value in attrs.values()))
        with base.inert_modules() as (spec, modules, declared, codes):
            sys.modules['celery.decorators'] = ModuleType('decorators')
            with self.assertRaises(identity.IdentityFailure):
                identity.verify_loaded_targets(spec)

    def test_driver_labels_only_and_scientific_bytes_preserved(self):
        for name in ('evaluator.py', 'observations.py', 'spec_builder.py', 'test_synthetic.py'):
            self.assertEqual(identity.sha256(HERE / name), identity.sha256(V2 / name))
        old_driver = (V2 / 'driver.py').read_bytes()
        self.assertEqual((HERE / 'driver.py').read_bytes(),
                         old_driver.replace(b'celery_completion_r094_v2', b'celery_completion_r094_v4'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    report = Path(args.report).resolve()
    if HERE not in report.parents or platform.python_version() != '3.12.10':
        raise ValueError('Use owned report path and actual Python3.12.10')
    if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
        raise ValueError('Use -I -S -B')
    adapter_before = {str(p): identity.sha256(p) for p in HERE.glob('*.py')}
    preserved = list(V2.rglob('*'))
    preserved += [REVIEW / name for name in ('NONAUTHOR_R80_V3_REVIEW.md',
                  'NONAUTHOR_R80_V3_REVIEW.json', 'test_virtual_modules.py')]
    preserved += list((base.PRIOR / 'protocols/celery_recovery/r080_native_v3').glob('*.py'))
    preserved += [base.original.PROTOCOL_PATH, base.original.RECIPE_PATH]
    preserved += [base.SOURCE / side / 'tree' / relative for side in ('before', 'after')
                  for relative in ('celery/local.py', 'celery/__init__.py')]
    baseline = {str(p): identity.sha256(p) for p in preserved if p.is_file()}
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(base.original.Tests),
        unittest.defaultTestLoader.loadTestsFromTestCase(base.ProvenanceTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(ReviewerRegressionTests)])
    old_profile = sys.getprofile()
    sys.setprofile(base.no_target_calls)
    try:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        sys.setprofile(old_profile)
    input_drift = [p for p, digest in baseline.items() if identity.sha256(p) != digest]
    adapter_drift = [p for p, digest in adapter_before.items() if identity.sha256(p) != digest]
    current_v2 = {str(p) for p in V2.rglob('*') if p.is_file()}
    previous_v2 = {p for p in baseline if Path(p).is_relative_to(V2)}
    passed = result.wasSuccessful() and not input_drift and not adapter_drift and current_v2 == previous_v2
    passed = passed and not base.ATTEMPTED_IMPORTS and not base.ATTEMPTED_TARGET_CALLS and not CALLS
    payload = dict(schema='R094_V3_AUTHOR_SYNTHETIC_QA_NOT_NATIVE_NOT_NONAUTHOR_REVIEW', passed=passed,
        python=platform.python_version(), executable=sys.executable, tests_run=result.testsRun,
        original_scientific_tests=14, inherited_provenance_tests=9, new_reviewer_regression_tests=9,
        failures=len(result.failures), errors=len(result.errors),
        attempted_target_imports=base.ATTEMPTED_IMPORTS, attempted_target_calls=base.ATTEMPTED_TARGET_CALLS,
        unexpected_synthetic_descriptor_calls=CALLS, target_imports=0, native_calls=0, network_calls=0,
        adapter_hashes=adapter_before, adapter_drift=adapter_drift,
        preserved_input_hashes=baseline, preserved_input_drift=input_drift,
        v2_membership_unchanged=current_v2 == previous_v2,
        reviewer_regressions_adapted=['generated_class_override_changes_export', 'same_file_factory_symbol_swap',
            'same_file_declared_function_substitution adapted as joint Proxy resolver substitution; r94 has no decorators export'],
        synthetic_boundary='Only inert synthetic modules/classes/proxies and uncalled statically compiled code objects. No native source was executed, imported, installed, patched or run. Added lookup/descriptor functions are author-defined fakes; verifier did not call them.',
        r80_fixed_or_rerun=False, independent_review_claimed=False, g3_started=False,
        failure_details=[text for _, text in result.failures + result.errors])
    with report.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: payload[k] for k in ('passed', 'tests_run', 'failures', 'errors')}))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
