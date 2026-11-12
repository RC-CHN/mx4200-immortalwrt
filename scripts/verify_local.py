#!/usr/bin/env python3
"""Verify built images and inspect their actual sysupgrade root filesystems."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile


REQUIRED = {
    'base-files', 'wpad-openssl', 'usteer', 'luci-app-usteer',
    'luci-theme-vantage', 'luci-app-vantage',
    'luci-i18n-vantage-zh-cn', 'luci-i18n-vantage-theme-zh-cn',
    'luci-proto-wireguard', 'wireguard-tools', 'kmod-wireguard', 'kmod-tun',
    'kmod-ath11k-ahb', 'kmod-usb3', 'kmod-usb-dwc3-qcom',
    'kmod-usb-storage-uas', 'kmod-fs-ext4', 'kmod-fs-exfat',
    'block-mount', 'usbutils', 'iperf3', 'tcpdump-mini',
    'kmod-inet-diag', 'kmod-netlink-diag', 'ip-full', 'dnsmasq-full',
    'nftables-json', 'kmod-nfnetlink-log',
    'kmod-fs-cifs', 'cifsmount', 'kmod-fs-ksmbd', 'ksmbd-server', 'luci-app-ksmbd',
    'kmod-fs-nfs-v3', 'kmod-fs-nfs-v4', 'kmod-fs-nfsd',
    'nfs-utils-v4', 'nfs-kernel-server-v4', 'nfs-kernel-server-utils', 'luci-app-nfs',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def output(argv):
    return subprocess.check_output(list(map(str, argv)), text=True).strip()


def aarch64(path):
    with path.open('rb') as stream:
        header = stream.read(20)
    require(header[:6] == b'\x7fELF\x02\x01' and
            int.from_bytes(header[18:20], 'little') == 183,
            f'Not an AArch64 ELF: {path}')


def verify(work, variant):
    source = work / 'sources' / ('immortalwrt' if variant == 'baseline' else 'immortalwrt-nss')
    artifact = work / 'artifacts' / variant
    target = artifact / 'bin/targets/qualcommax/ipq807x'
    host = source / 'staging_dir/host/bin'
    profiles = json.loads((target / 'profiles.json').read_text())
    lock = json.loads((artifact / 'build-record/sources.lock.json').read_text())
    requested = (artifact / 'build-record/requested.config').read_text()
    nft_packages = set(re.findall(r'^CONFIG_PACKAGE_(kmod-nft-[^=\n]+)=y$', requested, re.M))
    available_nft = set(re.findall(r'^Package: (kmod-nft-.+)$',
                                   (source / 'tmp/.packageinfo').read_text(), re.M))
    require(nft_packages == available_nft, 'Not all nftables extension packages are selected')
    require(profiles['git_commit'] == lock['source']['commit'], 'Source commit mismatch')
    module_cache = None
    if lock['build_revision'] >= 3:
        module_cache = json.loads((artifact / 'build-record/kernel-module-cache.json').read_text())
        require(module_cache['schema'] == 1 and module_cache['source_commit'] == profiles['git_commit'],
                'Missing compatible external-module rebuild record')
        require(module_cache['vermagic'] == profiles['linux_kernel']['vermagic'] and
                module_cache['kernel'] == 'linux-' + profiles['linux_kernel']['version'],
                'External-module cache ABI differs from image kernel')
    require(profiles['target'] == 'qualcommax/ipq807x', 'Wrong image target')
    require(set(profiles['profiles']) == {'linksys_homewrk', 'linksys_mx4300'}, 'Wrong device set')
    subprocess.run(['sha256sum', '--check', '--quiet', 'sha256sums'], cwd=target, check=True)
    reports = []
    scratch = work / 'verification'
    scratch.mkdir(exist_ok=True)
    for device, profile in profiles['profiles'].items():
        compatible = device.replace('_', ',', 1)
        for image in profile['images']:
            path = target / image['name']
            require(path.is_file() and path.stat().st_size == image['size'], f'Wrong size: {path}')
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            require(digest == image['sha256'], f'Wrong checksum: {path}')
        image = next(i for i in profile['images'] if i['type'] == 'sysupgrade')
        with tempfile.TemporaryDirectory(prefix=f'{variant}-{device}-', dir=scratch) as directory:
            directory = Path(directory)
            metadata = directory / 'metadata.json'
            subprocess.run([host / 'fwtool', '-i', metadata, target / image['name']], check=True)
            meta = json.loads(metadata.read_text())
            require(meta['supported_devices'] == [compatible], f'Wrong sysupgrade identity: {device}')
            # fwtool stores REVISION from getver.sh, whereas profiles.json uses
            # CONFIG_VERSION_CODE. A pinned shallow clone has an r0-<sha> ID.
            revision = subprocess.check_output([source / 'scripts/getver.sh'], cwd=source, text=True).strip()
            require(meta['version']['revision'] == revision, 'Wrong image source revision')
            require(meta['version']['board'] == device and meta['version']['target'] == profiles['target'],
                    'Wrong image board or target')
            with tarfile.open(target / image['name']) as archive:
                with archive.extractfile(f'sysupgrade-{device}/root') as stream:
                    with (directory / 'root.squashfs').open('wb') as destination:
                        shutil.copyfileobj(stream, destination)
            fs = directory / 'fs'
            # Device nodes are irrelevant to this payload inspection and need
            # root privileges to extract. All checked files live outside dev/.
            subprocess.run([host / 'unsquashfs4', '-no-progress', '-processors', '2',
                            '-excludes', '-dest', fs, directory / 'root.squashfs', 'dev'],
                           check=True, stdout=subprocess.DEVNULL)
            installed = (fs / 'lib/apk/db/installed').read_text()
            entries = {}
            for block in installed.split('\n\n'):
                fields = dict(re.findall(r'^([PVD]):(.*)$', block, re.M))
                if 'P' in fields:
                    entries[fields['P']] = fields
            packages = set(entries)
            # Inspect the delivered filesystem, including executable modes;
            # source overlays alone do not prove that the image contains them.
            overlay_files = {}
            for overlay in ('files', 'nss-files') if variant == 'nss' else ('files',):
                root = artifact / 'build-record/local-inputs' / overlay
                for item in root.rglob('*'):
                    if item.is_file():
                        overlay_files[item.relative_to(root)] = item
            for relative, original in overlay_files.items():
                delivered = fs / relative
                require(delivered.is_file() and delivered.read_bytes() == original.read_bytes(),
                        f'Custom image payload differs: {relative}')
                require(delivered.stat().st_mode & 0o111 == original.stat().st_mode & 0o111,
                        f'Custom executable mode differs: {relative}')
            require(profiles['version_code'] in (fs / 'usr/lib/os-release').read_text(),
                    'Wrong local firmware version')
            require(REQUIRED <= packages, f'{device}: missing packages {sorted(REQUIRED - packages)}')
            require('luci-theme-argon' not in packages, 'Old Argon package remains installed')
            require(not (fs / 'www/luci-static/argon/css/mx4300.css').exists(),
                    'Deleted Argon overlay remains in the image')
            require(not (fs / 'usr/share/ucode/luci/template/themes/argon/sysauth.ut').exists(),
                    'Deleted Argon login template remains in the image')
            require('/luci-static/vantage' in (fs / 'etc/uci-defaults/99-mx4300').read_text(),
                    'Vantage is not the clean-install default')
            require("option theme 'auto'" in (fs / 'etc/config/vantage_theme').read_text(),
                    'Vantage does not default to automatic colour mode')
            # The modern CSS must not be mangled by the legacy CSS minifier.
            css = source / 'feeds/vantage/luci-theme-vantage/htdocs/luci-static/vantage/vantage.css'
            require((fs / 'www/luci-static/vantage/vantage.css').read_bytes() == css.read_bytes(),
                    'Vantage CSS differs from the pinned source')
            menu = json.loads((fs / 'usr/share/luci/menu.d/zz-luci-app-vantage.json').read_text())
            require('admin/dashboard' in menu and 'admin/network/firewall/overview' not in menu,
                    'Incompatible optional Vantage firewall overview must not be exposed')
            require(nft_packages <= packages, f'{device}: missing nftables extensions')
            require(not {'sing-box', 'sing-box-tiny', 'luci-app-homeproxy', 'luci-app-openclash',
                         'luci-app-passwall', 'luci-app-passwall2'} & packages,
                    'Proxy applications must remain a separate user choice')
            require(not {'nfs-utils', 'nfs-kernel-server', 'dnsmasq'} & packages,
                    'Conflicting package variants in rootfs')
            require('luci-app-advanced-reboot' not in packages, 'Unexpected reboot partition selector')
            kernel = profiles['linux_kernel']['version']
            kernel_abi = (f'{kernel}~{profiles["linux_kernel"]["vermagic"]}'
                          f'-r{profiles["linux_kernel"]["release"]}')
            require(entries['kernel']['V'] == kernel_abi, 'Installed kernel ABI differs from image metadata')
            for name, fields in entries.items():
                if name.startswith('kmod-'):
                    require(f'kernel={kernel_abi}' in fields.get('D', '').split(),
                            f'Package {name} does not match the installed kernel ABI')
            modules = fs / 'lib/modules' / kernel
            for name in ('wireguard', 'ath11k', 'ath11k_ahb', 'xhci-hcd', 'dwc3-qcom', 'uas',
                         'tun', 'nft_tproxy', 'nft_socket', 'nft_meta_bridge',
                         'nft_queue', 'nft_compat', 'nfnetlink_log',
                         'cifs', 'ksmbd', 'nfs', 'nfsv3', 'nfsv4', 'nfsd'):
                module = modules / f'{name}.ko'
                aarch64(module)
                require(output(['modinfo', '-F', 'vermagic', module]).startswith(kernel + ' '),
                        f'Kernel mismatch: {name}')
            aarch64(fs / 'usr/bin/wg')
            aarch64(fs / 'usr/sbin/wpad')
            for binary in ('usr/sbin/mount.cifs', 'sbin/mount.nfs', 'usr/libexec/ksmbd.tools',
                           'usr/sbin/rpc.nfsd', 'usr/sbin/exportfs'):
                aarch64(fs / binary)
            require((fs / 'etc/uci-defaults/98-local-mesh').is_file(), 'Missing roaming startup policy')
            steering = (fs / 'etc/uci-defaults/98-local-mesh').read_text()
            require('/etc/init.d/usteer enable' in steering and
                    'usteer.@usteer[0].enabled=1' in steering and
                    '/tmp/mx4300-config-restored' in steering,
                    'Wrong usteer clean-install/upgrade policy')
            aarch64(fs / 'sbin/usteerd')
            service_policy = fs / 'etc/uci-defaults/99-local-services'
            original_policy = artifact / 'build-record/local-inputs/files/etc/uci-defaults/99-local-services'
            require(service_policy.read_bytes() == original_policy.read_bytes() and
                    service_policy.stat().st_mode & 0o111, 'Missing sharing startup policy')
            require(not re.search(r'^\s*[^#\s]', (fs / 'etc/exports').read_text(), re.M),
                    'Unexpected preconfigured NFS exports')
            require(not re.search(r'^\s*config\s+share\b', (fs / 'etc/config/ksmbd').read_text(), re.M),
                    'Unexpected preconfigured SMB shares')
            params = output(['modinfo', '-p', modules / 'ath11k.ko'])
            if variant == 'nss':
                require({'kmod-nss-wifi-drv', 'nss-firmware-ipq807x', 'ppe-help'} <= packages,
                        'Missing NSS payload')
                aarch64(modules / 'nss-wifi-drv.ko')
                require(output(['modinfo', '-F', 'vermagic', modules / 'nss-wifi-drv.ko']).startswith(kernel + ' '),
                        'NSS driver kernel mismatch')
                require('nss_offload:' in params, 'ath11k lacks NSS support')
                config = (fs / 'etc/config/nss-wifi').read_text()
                require("option offload '1'" in config and "option firmware '11.4'" in config,
                        'Wrong NSS defaults')
                for core in (0, 1):
                    require((fs / f'lib/firmware/qca-nss{core}-retail-11.4.bin').stat().st_size > 4096,
                            'Missing mesh-capable NSS firmware')
            else:
                require('kmod-nss-wifi-drv' not in packages and 'nss_offload:' not in params,
                        'Baseline unexpectedly contains NSS offload')
            reports.append({'device': device, 'compatible': compatible, 'images_verified': len(profile['images']),
                            'installed_packages': len(packages), 'kernel': kernel,
                            'sysupgrade_sha256': image['sha256'], 'nss_default_on': variant == 'nss',
                            'nft_extensions': sorted(nft_packages), 'sharing_default_off': True,
                            'theme': 'vantage', 'usteer_default_on': True,
                            'kernel_package_abi': kernel_abi})
    report = {'variant': variant, 'source_commit': profiles['git_commit'],
              'version_code': profiles['version_code'],
              'kernel': profiles['linux_kernel'], 'hardware_tested': False, 'devices': reports,
              'external_module_cache': module_cache}
    (artifact / 'build-record/verification.json').write_text(json.dumps(report, indent=2) + '\n')
    shutil.copy2(source / 'public-key.pem', artifact / 'build-record/public-key.pem')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=('baseline', 'nss', 'all'))
    parser.add_argument('--work', type=Path, default=Path('/data/mx4300-op'))
    args = parser.parse_args()
    for variant in ('baseline', 'nss') if args.variant == 'all' else (args.variant,):
        verify(args.work.resolve(), variant)
