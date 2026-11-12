"""Synchronize owned overlay files without erasing unrelated local files."""
import hashlib
import json
from pathlib import Path
import shutil


def inventory(roots):
    files = {}
    for root in roots:
        for path in root.rglob('*'):
            if path.is_symlink():
                raise ValueError(f'Overlay symlinks are not supported: {path}')
            if path.is_file():
                files[path.relative_to(root).as_posix()] = path
    return files


def fingerprint(path):
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode': path.stat().st_mode & 0o777}


def sync(roots, destination, state, previous_roots=()):
    """Adopt older build records once, then maintain a separate ownership record."""
    current = inventory(roots)
    previous = (json.loads(state.read_text()) if state.exists() else
                {name: fingerprint(path) for name, path in inventory(previous_roots).items()})
    desired = {name: fingerprint(path) for name, path in current.items()}
    # Preflight everything before deleting or replacing a file.
    for name in previous.keys() | desired.keys():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError(f'Invalid overlay path: {name}')
        target = destination / name
        if any(parent.is_symlink() for parent in (target, *target.parents)):
            raise ValueError(f'Symlink in overlay destination: {target}')
        if target.exists():
            if not target.is_file():
                raise ValueError(f'Overlay target is not a file: {target}')
            actual = fingerprint(target)
            if actual != previous.get(name) and actual != desired.get(name):
                raise ValueError(f'Locally modified or unowned overlay file: {target}')
    for name in previous.keys() - current.keys():
        (destination / name).unlink(missing_ok=True)
    for name, original in current.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
    state.parent.mkdir(parents=True, exist_ok=True)
    temporary = state.with_suffix('.tmp')
    temporary.write_text(json.dumps(desired, indent=2, sort_keys=True) + '\n')
    temporary.replace(state)
