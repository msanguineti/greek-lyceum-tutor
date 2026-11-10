#!/usr/bin/env python3
"""Build deterministic explicit-field packages; unready fields cannot enter release output."""
import argparse
import hashlib
import json
import posixpath
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from products import ROOT, catalog, profile
from stage import json_bytes, stage
from validate import markdown_link_destinations, validate


def write_archive(path, prefix, payload):
    """Fixed order, timestamps, modes and compression make bytes reproducible."""
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(f'{prefix}/{name}', date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(payload)
        assert set(archive.namelist()) == {f'{prefix}/{name}' for name in payload}
        for name, data in payload.items():
            assert archive.read(f'{prefix}/{name}') == data
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix('.zip.sha256').write_text(f'{sha}  {path.name}\n')
    print(f'PASS: archive inventory, CRC and bytes inspected: {path}\nSHA256 {sha}')
    return sha


def marketplace_entry(field):
    return {'name': field['name'],
            'source': {'source': 'local', 'path': f"./plugins/{field['name']}"},
            'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
            'category': 'Education'}


def checked_runtime(field, destination):
    stage(field, destination)
    manifest, files = validate(destination, field)
    payload = {p.relative_to(destination).as_posix(): p.read_bytes() for p in files}
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        payload[name] = (ROOT / name).read_bytes()
    assert json.loads(payload['plugin.json']) == manifest
    return payload


def desktop_payload(field, runtime):
    """Preserve the existing field-2 desktop bundle; other fields use marketplace trees."""
    assert field['number'] == '2'
    name = field['name']
    marketplace = json.loads((ROOT / 'distribution/marketplace.json').read_text())
    assert marketplace['name'] == name
    assert marketplace['plugins'] == [marketplace_entry(field)]
    payload = {f'plugins/{name}/{path}': content for path, content in runtime.items()}
    payload['.agents/plugins/marketplace.json'] = (ROOT / 'distribution/marketplace.json').read_bytes()
    for path in ('README.md', 'USAGE.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
                 'docs/design.md', 'docs/status.md', 'docs/development.md'):
        text = (ROOT / path).read_text()
        if path.endswith('.md'):
            text = text.replace('](skills/', f'](plugins/{name}/skills/')
            text = text.replace('](../skills/', f'](../plugins/{name}/skills/')
        payload[path] = text.encode()
    import re
    for name, content in payload.items():
        if not name.endswith('.md'):
            continue
        for target in re.findall(r'\]\(([^)]+)\)', content.decode()):
            if target.startswith(('https://', 'http://', '#')):
                continue
            resolved = posixpath.normpath(str(PurePosixPath(name).parent / target.split('#')[0]))
            assert resolved in payload, f'{name}: missing bundle link {target}'
    return payload


def download_readme(field):
    labels = catalog()['authoring']
    subjects = ', '.join(labels[role]['label'] for role in field['subjects'])
    return f"""# {field['display_name']}

Βοηθός μελέτης στα ελληνικά για τη Γ΄ ΓΕΛ και τις Πανελλαδικές 2027.
Μαθήματα: {subjects}. Προσφέρει εξηγήσεις, υποδείξεις, έλεγχο προσπάθειας, οργάνωση μελέτης και εξάσκηση εξετάσεων.

## Εγκατάσταση χωρίς Plugin Creator

Χρησιμοποίησε το ChatGPT από browser ή την εφαρμογή για υπολογιστή. Δεν χρειάζεσαι Business λογαριασμό, Plugin Creator, κλειδί API ή δικό σου server· χρειάζεται να είναι διαθέσιμη η επιλογή προσθήκης plugins στον λογαριασμό σου.

1. Κράτησε το ZIP χωρίς αποσυμπίεση.
2. Στο ChatGPT άνοιξε **Plugins** και την επιλογή προσθήκης (**+** ή **Add**).
3. Επίλεξε **Upload plugin archive** ή την αντίστοιχη επιλογή μεταφόρτωσης ZIP και διάλεξε το αρχείο.
4. Ολοκλήρωσε τα βήματα που εμφανίζονται. Αν υπάρχει κουμπί **Install / Εγκατάσταση**, πάτησέ το.

Αν δεν βλέπεις την επιλογή μεταφόρτωσης, δοκίμασε την εφαρμογή υπολογιστή ή το ChatGPT από browser. Οι ονομασίες και οι διαθέσιμες επιλογές διαφέρουν ανά έκδοση και λογαριασμό. Η επισύναψη του ZIP μέσα σε συνομιλία δεν εγκαθιστά τον tutor.

## Πρώτη χρήση

Άνοιξε νέα συνομιλία, επίλεξε τον tutor με `@` και γράψε το μάθημα και τι χρειάζεσαι. Για παράδειγμα:

- «Κόλλησα σε αυτή την άσκηση. Θα σου γράψω τι δοκίμασα· δώσε μόνο μία υπόδειξη.»
- «Εξήγησέ το σύντομα, με ένα απλό παράδειγμα.»
- «Φτιάξε μια πρωτότυπη δοκιμασία 20 μονάδων, χωρίς λύσεις. Περίμενε τις απαντήσεις μου.»

Συνήθως ο tutor δίνει ένα μικρό βήμα ή μία υπόδειξη κάθε φορά. Μπορείς να ζητήσεις πλήρη λύση, πιο σύντομη απάντηση ή διόρθωση χωρίς βαθμό. Νέες ασκήσεις και δοκιμασίες δημιουργούνται όταν τις ζητήσεις.

Για συγκεκριμένη άσκηση, δώσε την εκφώνηση και την προσπάθειά σου· αν είναι από βιβλίο, πρόσθεσε τίτλο και σελίδα. Δες τον [σύντομο οδηγό χρήσης](USAGE.md) για περισσότερα παραδείγματα.

## Χρήσιμες διευκρινίσεις

Ο tutor είναι πειραματικό βοήθημα και μπορεί να κάνει λάθη, ακόμη και σε διόρθωση ή υπολογισμό. Έλεγχε κρίσιμες απαντήσεις με τον εκπαιδευτικό και την επίσημη πηγή. Δεν αντικαθιστά τη διδασκαλία, δεν προβλέπει θέματα και δεν δίνει επίσημη βαθμολογία.

Τα βιβλία και τα πλήρη εξεταστικά φυλλάδια παρέχονται με επίσημους συνδέσμους. Αν μια πηγή δεν είναι προσβάσιμη, μπορεί να χρειαστεί να δώσεις το απαραίτητο απόσπασμα. Περιήγηση, εικόνες, γραφήματα και αρχεία εξαρτώνται από τις δυνατότητες του ChatGPT στον λογαριασμό σου.

Δεν αποθηκεύεται αυτόματα προσωπικό αρχείο προόδου από το plugin. Οι συνομιλίες ακολουθούν τις ρυθμίσεις του ChatGPT. Μια νέα λήψη δεν ενημερώνει αυτόματα έναν ήδη εγκατεστημένο tutor.

Το πρωτότυπο υλικό διατίθεται με άδεια [MIT](LICENSE). Το επίσημο εκπαιδευτικό υλικό διατηρεί τους δικούς του όρους· δες τις [αναφορές τρίτων](THIRD_PARTY_NOTICES.md).
""".encode()


def download_payload(field, runtime):
    # A download is one portable plugin, not a marketplace wrapped around it.
    payload = dict(runtime)
    payload['README.md'] = download_readme(field)
    payload['USAGE.md'] = (ROOT / 'USAGE.md').read_bytes()
    for path, content in payload.items():
        if path.endswith('.md'):
            for target in markdown_link_destinations(content.decode()):
                if target.startswith(('https://', 'http://', '#')):
                    continue
                resolved = posixpath.normpath(str(PurePosixPath(path).parent / target.split('#')[0]))
                assert resolved in payload, f'{path}: missing bundle link {target}'
    assert set(payload) == set(runtime) | {'README.md', 'USAGE.md'}
    return payload


def build_download_bundle(number, output_dir=None):
    """One directly uploadable plugin, its exact portable runtime, and human guides."""
    field = profile(number, release=True)
    with tempfile.TemporaryDirectory(prefix='lyceum-download-') as temporary:
        runtime = checked_runtime(field, Path(temporary) / 'plugin')
        payload = download_payload(field, runtime)
    output_dir = ROOT / '.dist' if output_dir is None else Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"panelladikes-field-{field['number']}"
    archive = output_dir / f"{prefix}-{field['version']}.zip"
    write_archive(archive, field['name'], payload)
    return archive


def build(number='2', output_dir=None, *, candidate=False, desktop=True):
    field = profile(number, release=not candidate)
    output_dir = ROOT / '.dist' if output_dir is None else Path(output_dir)
    # Do not mix private candidates with an installable/release tree.
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lyceum-stage-') as temporary:
        runtime = checked_runtime(field, Path(temporary) / 'plugin')
    suffix = '-candidate' if candidate else ''
    archive = output_dir / f"{field['name']}-{field['version']}{suffix}.zip"
    write_archive(archive, field['name'], runtime)
    if desktop and field['number'] == '2' and not candidate:
        path = output_dir / f"{field['name']}-{field['version']}-desktop.zip"
        write_archive(path, field['name'] + '-desktop', desktop_payload(field, runtime))
    return archive


def build_marketplace(destination):
    """Materialize actual, validated release-ready plugin directories only."""
    destination = Path(destination)
    assert not destination.exists(), 'Marketplace destination must not exist'
    fields = []
    for number in catalog()['fields']:
        if catalog()['fields'][number]['release_ready']:
            fields.append(profile(number, release=True))
    assert fields, 'No release-ready fields'
    # Assemble and validate away from the final tree, so a failure cannot expose a partial tree.
    with tempfile.TemporaryDirectory(prefix='lyceum-marketplace-') as temporary:
        tree = Path(temporary) / 'tree'
        entries = []
        for field in fields:
            plugin = tree / 'plugins' / field['name']
            runtime = checked_runtime(field, plugin)
            for name, content in download_payload(field, runtime).items():
                (plugin / name).write_bytes(content)
            entries.append(marketplace_entry(field))
        manifest = {'name': 'greek-lyceum-tutor',
                    'interface': {'displayName': 'Πανελλαδικές — Επιλογή πεδίου'},
                    'plugins': entries}
        manifest_path = tree / '.agents/plugins/marketplace.json'
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_bytes(json_bytes(manifest))
        for entry in manifest['plugins']:
            source = tree / entry['source']['path']
            assert (source / 'plugin.json').is_file()
            assert source.resolve().is_relative_to(tree.resolve())
        shutil.copytree(tree, destination)
    print(f'PASS: self-contained marketplace tree; {len(entries)} ready fields: {destination}')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--field', choices=['1', '2', '3', '4'], default='2')
    parser.add_argument('--output-dir', type=Path, help='Use a disposable directory to keep archives out of Git')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--candidate', action='store_true', help='Private unready build, never included in a marketplace')
    mode.add_argument('--download-bundle', action='store_true', help='Build one directly uploadable release-ready field ZIP only')
    parser.add_argument('--marketplace', type=Path, help='Build an additional self-contained tree of release-ready fields')
    args = parser.parse_args()
    assert not (args.candidate and args.marketplace), 'Private candidates cannot create marketplace trees'
    assert not (args.download_bundle and args.marketplace), 'Download mode produces only one field bundle'
    if args.download_bundle:
        build_download_bundle(args.field, args.output_dir)
        return
    build(args.field, args.output_dir, candidate=args.candidate)
    if args.marketplace:
        build_marketplace(args.marketplace)


if __name__ == '__main__':
    main()
