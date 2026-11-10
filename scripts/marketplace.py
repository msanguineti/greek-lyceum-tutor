#!/usr/bin/env python3
"""Synchronize the published marketplace from the canonical authoring sources."""
import argparse
import shutil
import tempfile
from pathlib import Path

from package import build_marketplace
from products import ROOT


def files(root):
    paths = [root / '.agents/plugins/marketplace.json']
    plugins = root / 'plugins'
    assert not plugins.is_symlink(), 'Marketplace plugins directory cannot be a symlink'
    if plugins.exists():
        paths.extend(plugins.rglob('*'))
    assert not any(path.is_symlink() for path in paths), 'Marketplace cannot contain symlinks'
    return {path.relative_to(root): path.read_bytes() for path in paths if path.is_file()}


def sync(repository=ROOT, *, check=False):
    repository = Path(repository)
    with tempfile.TemporaryDirectory(prefix='lyceum-marketplace-sync-') as temporary:
        tree = build_marketplace(Path(temporary) / 'marketplace')
        expected = files(tree)
        actual = files(repository)
        if check:
            differences = sorted(str(path) for path in expected.keys() | actual.keys()
                                 if expected.get(path) != actual.get(path))
            assert not differences, 'Marketplace out of sync: ' + ', '.join(differences[:8])
        else:
            plugins = repository / 'plugins'
            if plugins.exists():
                shutil.rmtree(plugins)
            shutil.copytree(tree / 'plugins', plugins)
            manifest = repository / '.agents/plugins/marketplace.json'
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_bytes(expected[Path('.agents/plugins/marketplace.json')])
            assert files(repository) == expected, 'Marketplace synchronization failed'
    print('PASS: repository marketplace matches the selected authoring sources')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Reject missing, changed or extra published files')
    sync(check=parser.parse_args().check)
