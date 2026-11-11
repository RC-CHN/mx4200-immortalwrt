"""Regression: a new kernel ABI must not reuse old external module objects."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from kernel_module_cache import prepare_module_cache, selected_module_sources

CONFIG = 'CONFIG_PACKAGE_kmod-nss-wifi-drv=y\nCONFIG_PACKAGE_kmod-ath11k=m\nCONFIG_PACKAGE_kmod-wireguard=y\n'
META = '''Source-Makefile: package/kernel/nss-wifi-drv/Makefile
Package: kmod-nss-wifi-drv
Source-Makefile: package/kernel/mac80211/Makefile
Package: kmod-ath11k
Package: kmod-unused
Source-Makefile: package/kernel/linux/Makefile
Package: kmod-wireguard
Source-Makefile: package/feeds/packages/unselected/Makefile
Package: kmod-unselected
'''


class KernelModuleCacheTests(unittest.TestCase):
    def test_only_selected_external_sources_are_cleaned(self):
        self.assertEqual(selected_module_sources(CONFIG, META),
                         ['package/kernel/mac80211', 'package/kernel/nss-wifi-drv'])

    def test_changed_abi_is_read_after_kernel_prepare_and_not_marked_success(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            magic = source / 'build_dir/target-test/linux-qualcommax_ipq807x/linux-6.18.60/.vermagic'
            magic.parent.mkdir(parents=True)
            magic.write_text('a' * 32)
            (source / 'tmp').mkdir()
            (source / '.config').write_text(CONFIG)
            (source / 'tmp/.packageinfo').write_text(META)
            state = source / 'state.json'
            previous = {'schema': 1, 'source_commit': 'commit', 'kernel': 'linux-6.18.60', 'vermagic': 'a' * 32}
            state.write_text(json.dumps(previous))
            calls = []

            def run(label, args):
                calls.append((label, args))
                if label == 'kernel-prepare':
                    magic.write_text('b' * 32)

            current = prepare_module_cache(source, state, 'commit', run, 52)
            self.assertEqual(current['vermagic'], 'b' * 32)
            self.assertEqual([c[0] for c in calls], ['kernel-prepare', 'kernel-module-clean'])
            self.assertEqual(json.loads(state.read_text()), previous)
            state.write_text(json.dumps(current))
            calls.clear()
            prepare_module_cache(source, state, 'commit', run, 52)
            self.assertEqual([c[0] for c in calls], ['kernel-prepare'])
            state.unlink()
            calls.clear()
            prepare_module_cache(source, state, 'commit', run, 52)
            self.assertEqual([c[0] for c in calls], ['kernel-prepare', 'kernel-module-clean'])

    def test_rejects_package_paths_outside_source_tree(self):
        with self.assertRaises(ValueError):
            selected_module_sources(CONFIG, 'Source-Makefile: ../outside/Makefile\nPackage: kmod-nss-wifi-drv\n')


if __name__ == '__main__':
    unittest.main()
