"""Invalidate external kernel modules when their kernel ABI changes."""
import json
from pathlib import PurePosixPath
import re


def selected_module_sources(config, metadata):
    selected = set(re.findall(r'^CONFIG_PACKAGE_(kmod-[^=\n]+)=[ym]$', config, re.M))
    sources = set()
    source = None
    for line in metadata.splitlines():
        if line.startswith('Source-Makefile: '):
            source = PurePosixPath(line.removeprefix('Source-Makefile: '))
            if source.is_absolute() or '..' in source.parts or not source.parts or source.parts[0] != 'package' or source.name != 'Makefile':
                raise ValueError(f'Invalid package source: {source}')
        elif line.startswith('Package: ') and line.removeprefix('Package: ') in selected:
            if source is None:
                raise ValueError('Kernel package has no Source-Makefile')
            if source.parent != PurePosixPath('package/kernel/linux'):
                sources.add(str(source.parent))
    return sorted(sources)


def prepare_module_cache(source, state_file, source_commit, run, jobs):
    # Finalise headers before consulting .vermagic or compiling external
    # modules. New package ABI metadata does not invalidate cached .o files.
    run('kernel-prepare', ['make', f'-j{jobs}', 'target/linux/compile', 'V=s'])
    magic_files = list((source / 'build_dir').glob('target-*/linux-qualcommax_ipq807x/linux-*/.vermagic'))
    if len(magic_files) != 1:
        raise ValueError('Expected one configured kernel ABI')
    magic = magic_files[0].read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{32}', magic):
        raise ValueError('Missing or invalid configured kernel ABI')
    identity = {'schema': 1, 'source_commit': source_commit,
                'kernel': magic_files[0].parent.name, 'vermagic': magic}
    try:
        previous = json.loads(state_file.read_text())
    except (FileNotFoundError, ValueError):
        previous = None
    if previous != identity:
        sources = selected_module_sources((source / '.config').read_text(),
                                          (source / 'tmp/.packageinfo').read_text())
        if sources:
            run('kernel-module-clean', ['make', *[p + '/clean' for p in sources], 'V=s'])
    # Only the caller's successful complete build may mark the cache current.
    return identity
