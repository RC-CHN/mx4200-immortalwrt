#!/usr/bin/env python3
"""Run pinned Vantage tests with the MX4300 code overlays, without a router."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OVERLAYS = {
    'usr/share/ucode/luci/template/themes/vantage/sysauth.ut':
        'luci-theme-vantage/ucode/template/themes/vantage/sysauth.ut',
    'www/luci-static/resources/vantage-theme/host.js':
        'luci-theme-vantage/htdocs/luci-static/resources/vantage-theme/host.js',
    'usr/share/rpcd/ucode/luci.vantage':
        'luci-app-vantage/root/usr/share/rpcd/ucode/luci.vantage',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    source = work / 'sources/immortalwrt-nss'
    feed = source / 'feeds/vantage'
    lock = json.loads((ROOT / 'local/sources.lock.json').read_text())
    commit = subprocess.check_output(['git', '-C', str(feed), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != lock['feeds']['vantage']['commit']:
        raise ValueError('Vantage feed does not match sources.lock.json')
    ucode = source / 'staging_dir/hostpkg/bin/ucode'
    target = work / 'artifacts/nss/bin/targets/qualcommax/ipq807x'
    if not (target / 'profiles.json').is_file() or not ucode.is_file():
        raise ValueError('Build the NSS image first to supply the real rootfs and host ucode')
    with tempfile.TemporaryDirectory(prefix='vantage-check-', dir=work / 'tmp') as temporary:
        rootfs = Path(temporary) / 'rootfs'
        profiles = json.loads((target / 'profiles.json').read_text())
        image = next(i['name'] for i in profiles['profiles']['linksys_homewrk']['images']
                     if i['type'] == 'sysupgrade')
        squashfs = Path(temporary) / 'root.squashfs'
        with tarfile.open(target / image) as archive:
            with archive.extractfile('sysupgrade-linksys_homewrk/root') as original:
                with squashfs.open('wb') as output:
                    shutil.copyfileobj(original, output)
        subprocess.run([source / 'staging_dir/host/bin/unsquashfs4', '-no-progress',
                        '-processors', '2', '-excludes', '-dest', rootfs, squashfs, 'dev'],
                       check=True, stdout=subprocess.DEVNULL)
        # LuCI compiles .ut files to ucode bytecode in the image; the upstream
        # JavaScript template harness needs their corresponding pinned source.
        shutil.copytree(source / 'feeds/luci/modules/luci-base/ucode/template',
                        rootfs / 'usr/share/ucode/luci/template', dirs_exist_ok=True)
        env = dict(os.environ, UCODE=str(ucode), VANTAGE_ROOTFS=str(rootfs))
        checkout = Path(temporary) / 'source'
        shutil.copytree(feed, checkout, ignore=shutil.ignore_patterns('.git'))
        # The upstream address scanner uses git ls-files, including untracked
        # files. A fresh local repository suffices; no commits or remotes.
        subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
        for original, destination in OVERLAYS.items():
            shutil.copy2(ROOT / 'local/files' / original, checkout / destination)
        # The local login deliberately shows the same encoded hostname in its
        # title and heading. Preserve all upstream injection/privacy assertions.
        security_test = checkout / 'security-tests/test_templates.js'
        text = security_test.read_text()
        old = "assert.equal(good.html.split(SECRET.hostname).length - 1, 1, 'the hostname once');"
        if old not in text:
            raise ValueError('Review the changed upstream login test before updating the pin')
        text = text.replace(old, "assert.equal(good.html.split(SECRET.hostname).length - 1, 2, 'hostname in title and heading');\n"
                            "\tassert.match(good.html, /<title>Log in · SECRET-HOSTNAME<\\/title>/);")
        security_test.write_text(text)
        # This optional page is not exposed by our menu overlay: its old-fw4
        # regression assumes negated protocols are ignored. Our fw4 implements
        # them. Keep the incompatibility explicit, rather than changing fw4 or
        # rewriting upstream's expected results. verify_local checks the menu.
        commands = [
            ['node', '--test', '--test-skip-pattern',
             "^fw4 itself: the regressions' openings", 'tests/'],
            ['node', 'security-tests/check_dom_sinks.js'],
            ['node', 'security-tests/test_templates.js'],
            ['node', 'security-tests/test_acl_policy.js'],
            ['node', 'security-tests/check_private_addresses.js'],
            ['bash', 'dev/i18n/update.sh', '--check'],
        ]
        for command in commands:
            print('+ ' + ' '.join(command), flush=True)
            subprocess.run(command, cwd=checkout, env=env, check=True)


if __name__ == '__main__':
    main()
