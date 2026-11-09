#!/usr/bin/env python3
"""Build pinned HomeWRK/MX4300 images natively on a Linux build host."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_defaults import check
from homewrk_dts import prepare as protect_homewrk


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=('baseline', 'nss'))
    parser.add_argument('stage', choices=('prepare', 'download', 'toolchain', 'compile', 'collect', 'all'))
    parser.add_argument('--work', type=Path, default=Path('/data/mx4300-op'))
    parser.add_argument('-j', '--jobs', type=int, default=min(16, os.cpu_count() or 1))
    network = parser.add_mutually_exclusive_group()
    network.add_argument('--no-proxy', action='store_true', help='use direct connections for this build')
    network.add_argument('--proxy', help='HTTP or SOCKS proxy URL for this build')
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('jobs must be positive')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    build_lock = (work / f'.{args.variant}.lock').open('a')
    try:
        fcntl.flock(build_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f'Another {args.variant} build is active in {work}')
    if args.stage != 'collect' and shutil.disk_usage(work).free < 30 * 1024**3:
        sys.exit('At least 30 GiB free space is required in the build directory.')
    for name in ('sources', 'logs', 'downloads', 'tmp', 'ccache', 'artifacts'):
        (work / name).mkdir(exist_ok=True)
    # OpenWrt locks downloads under each source tree's tmp/, while partial
    # archives live in dl/. Sharing a writable dl/ across trees races.
    downloads = work / 'downloads' / args.variant
    downloads.mkdir(exist_ok=True)
    source = work / 'sources' / ('immortalwrt' if args.variant == 'baseline' else 'immortalwrt-nss')
    lock = json.loads((ROOT / 'local/sources.lock.json').read_text())
    if not {'packages', 'luci', 'routing', 'telephony', 'nss'} <= lock['feeds'].keys():
        sys.exit('The feed lock is incomplete; record reviewed feed commits first.')
    env = dict(os.environ, TMPDIR=str(work / 'tmp'), LC_ALL='C.UTF-8')
    env.pop('MAKEFLAGS', None)
    if args.no_proxy or args.proxy:
        for key in ('http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
            env.pop(key, None)
    if args.proxy:
        for key in ('http_proxy', 'https_proxy', 'all_proxy'):
            env[key] = args.proxy

    def run(label, argv, cwd=source):
        log = work / 'logs' / f'{args.variant}-{label}.log'
        print(f'{label}: {" ".join(map(str, argv))}\n  log: {log}', flush=True)
        with log.open('a') as output:
            output.write(f'\n[{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}] {argv!r}\n')
            output.flush()
            subprocess.run(list(map(str, argv)), cwd=cwd, env=env, stdout=output,
                           stderr=subprocess.STDOUT, check=True)

    def ensure_checkout(path, spec, reference=None):
        if not path.exists():
            if reference and (reference / '.git').exists() and git(reference, 'rev-parse', 'HEAD') == spec['commit']:
                run('clone-' + path.name, ['git', 'clone', '--no-hardlinks', reference, path], work)
                run('remote-' + path.name, ['git', 'remote', 'set-url', 'origin', spec['url']], path)
            else:
                path.mkdir(parents=True)
                run('init-' + path.name, ['git', 'init', path], work)
                run('remote-' + path.name, ['git', 'remote', 'add', 'origin', spec['url']], path)
                run('fetch-' + path.name, ['git', '-c', 'http.version=HTTP/1.1', 'fetch', '--depth=1',
                                          'origin', spec['commit']], path)
                run('checkout-' + path.name, ['git', 'checkout', '--detach', spec['commit']], path)
        actual = git(path, 'rev-parse', 'HEAD')
        if actual != spec['commit']:
            raise ValueError(f'{path}: expected {spec["commit"]}, got {actual}; refusing to reset it')

    def configure():
        ensure_checkout(source, lock['source'])
        if args.variant == 'nss':
            patch = ROOT / 'local/patches/nss-wifi.patch'
            if hashlib.sha256(patch.read_bytes()).hexdigest() != lock['nss_reference']['patch_sha256']:
                raise ValueError('NSS patch hash differs from the source lock')
            applied = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)],
                                     cwd=source, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if applied.returncode:
                run('nss-check', ['git', 'apply', '--check', patch])
                run('nss-apply', ['git', 'apply', patch])
        elif (source / 'package/kernel/nss-wifi-drv').exists():
            raise ValueError('The baseline source contains NSS changes; use a separate build tree')
        protect_homewrk(source)
        dl = source / 'dl'
        if dl.is_symlink() and dl.resolve() != downloads:
            raise ValueError(f'{dl} must point to the isolated cache {downloads}')
        if not dl.exists() and not dl.is_symlink():
            dl.symlink_to(downloads, target_is_directory=True)
        feeds = source / 'feeds'
        feeds.mkdir(exist_ok=True)
        selected = {k: v for k, v in lock['feeds'].items() if args.variant == 'nss' or k != 'nss'}
        for name, spec in selected.items():
            reference = work / 'sources/immortalwrt/feeds' / name if args.variant == 'nss' else None
            ensure_checkout(feeds / name, spec, reference)
            if git(feeds / name, 'status', '--porcelain', '--untracked-files=no'):
                raise ValueError(f'Feed {name} has unrecorded recipe changes')
        (source / 'feeds.conf').write_text(''.join(
            f'src-git {name} {spec["url"]}^{spec["commit"]}\n' for name, spec in selected.items()))
        run('feeds-index', ['./scripts/feeds', 'update', '-i'])
        run('feeds-install', ['./scripts/feeds', 'install', '-a'])
        requested = (ROOT / 'local/mesh.config').read_text()
        if args.variant == 'nss':
            requested += '\n' + (ROOT / 'local/nss.config').read_text()
        requested += (f'\nCONFIG_CCACHE_DIR="{work / "ccache"}"\nCONFIG_VERSIONOPT=y\n'
                      f'CONFIG_VERSION_CODE="local-{args.variant}-{lock["source"]["commit"][:12]}'
                      f'-r{lock["build_revision"]}"\n')
        (source / '.config').write_text(requested)
        shutil.copytree(ROOT / 'local/files', source / 'files', dirs_exist_ok=True)
        if args.variant == 'nss':
            shutil.copytree(ROOT / 'local/nss-files', source / 'files', dirs_exist_ok=True)
        run('defconfig', ['make', 'defconfig'])
        check((source / '.config').read_text(), (source / 'tmp/.packageinfo').read_text(), requested)
        record = work / 'artifacts' / args.variant / 'build-record'
        record.mkdir(parents=True, exist_ok=True)
        (record / 'requested.config').write_text(requested)
        shutil.copy2(source / '.config', record / 'resolved.config')
        shutil.copy2(ROOT / 'local/sources.lock.json', record)
        shutil.copy2(source / 'feeds.conf', record)
        shutil.copytree(ROOT / 'local', record / 'local-inputs', dirs_exist_ok=True)
        for name in ('build_local.py', 'homewrk_dts.py', 'check_defaults.py'):
            shutil.copy2(ROOT / 'scripts' / name, record / name)
        (record / 'source.diff').write_text(git(source, 'diff', '--binary') + '\n')
        print('Configuration and requested package checks passed.', flush=True)

    def collect():
        target = source / 'bin/targets/qualcommax/ipq807x'
        profiles = json.loads((target / 'profiles.json').read_text())
        if set(profiles['profiles']) != {'linksys_homewrk', 'linksys_mx4300'}:
            raise ValueError('Unexpected device profiles in output; refusing to mix firmware images')
        for name in ('linksys_homewrk', 'linksys_mx4300'):
            profile = profiles['profiles'][name]
            images = profile['images']
            if not any('sysupgrade' in i['name'] for i in images):
                raise ValueError(f'{name}: sysupgrade image is missing')
            if not any('initramfs' in i['name'] for i in images):
                raise ValueError(f'{name}: temporary boot image is missing')
            for item in images:
                image = target / item['name']
                if not image.is_file() or image.stat().st_size == 0:
                    raise ValueError(f'Missing or empty image: {image}')
                if hashlib.sha256(image.read_bytes()).hexdigest() != item['sha256']:
                    raise ValueError(f'Image checksum mismatch: {image}')
        destination = work / 'artifacts' / args.variant
        shutil.copytree(source / 'bin', destination / 'bin', dirs_exist_ok=True)
        print(f'Images and matching package repositories: {destination / "bin"}', flush=True)

    if args.stage == 'collect':
        collect()
        return
    configure()
    if args.stage in ('download', 'all'):
        run('download', ['make', f'-j{min(args.jobs, 8)}', 'download', 'V=s'])
    if args.stage in ('toolchain', 'all'):
        run('tools', ['make', f'-j{args.jobs}', 'tools/install', 'V=s'])
        run('toolchain', ['make', f'-j{args.jobs}', 'toolchain/install', 'V=s'])
    if args.stage in ('compile', 'all'):
        run('compile', ['make', f'-j{args.jobs}', 'V=s'])
        collect()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(f'Build stopped: {error}')
