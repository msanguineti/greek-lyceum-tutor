"""Explicit source inventory and field contracts. Nothing here is a runtime dependency."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'distribution/products.json'
# Subjects using the original shared source/textbook metadata schema.
# This distinction is independent of the unified authoring directory layout.
LEGACY_SUBJECTS = {'greek', 'mathematics', 'physics', 'chemistry'}
REVIEW_FILES = {'mathematics': 'reviewed-math.json', 'physics': 'reviewed-physics.json',
                'chemistry': 'reviewed-chemistry.json', 'greek': 'reviewed-greek.json'}
FIELD_SUBJECTS = {
    '1': {'greek', 'ancient-greek', 'history', 'latin'},
    '2': {'greek', 'mathematics', 'physics', 'chemistry'},
    '3': {'greek', 'physics', 'chemistry', 'biology'},
    '4': {'greek', 'mathematics', 'economics', 'informatics'},
}


def catalog():
    data = json.loads(CATALOG.read_text())
    assert data['schema_version'] == 1
    assert set(data['fields']) == {'1', '2', '3', '4'}
    emitted = set()
    identities = set()
    for number, field in data['fields'].items():
        assert field['icon'] == f'assets/icons/field-{number}.png', 'Wrong field icon source'
        assert re.fullmatch(r'[0-9a-f]{64}', field['icon_sha256']), 'Invalid field icon hash'
        assert isinstance(field.get('release_ready'), bool), 'Missing field readiness'
        assert len(field['subjects']) == len(set(field['subjects'])) == 4
        assert set(field['subjects']) == FIELD_SUBJECTS[number], 'Wrong subjects for scientific field'
        assert set(field['skill_names']) == {'study', 'exams', *field['subjects']}
        assert field['name'] not in identities, 'Duplicate plugin identity'
        identities.add(field['name'])
        for role, name in field['skill_names'].items():
            assert role in data['authoring'], f'Unknown subject: {role}'
            assert isinstance(data['authoring'][role].get('ready'), bool), 'Missing subject readiness'
            assert name not in emitted, 'Duplicate emitted skill name'
            emitted.add(name)
            if number == '2':
                assert name == 'lyceum-' + role, 'Existing skill identity changed'
            else:
                assert name == f'lyceum-f{number}-{role}', 'All new skills require a field namespace'
    assert data['fields']['2']['name'] == 'greek-lyceum-tutor', 'Existing plugin identity changed'
    for role, source in data['authoring'].items():
        assert source['source'] == 'skills/lyceum-' + role, 'Authoring sources must use the skills root'
        assert len(source['files']) == len(set(source['files']))
        for path in source['files']:
            assert not Path(path).is_absolute() and '..' not in Path(path).parts
            assert not any(part.startswith('.') for part in Path(path).parts)
    return data


def profile(number='2', *, release=False):
    data = catalog()
    number = str(number)
    assert number in data['fields'], f'Unknown field: {number}'
    field = dict(data['fields'][number], number=number)
    if release:
        assert field['release_ready'], f'Field {number} is not release-ready'
        for role in field['skill_names']:
            assert data['authoring'][role]['ready'], f'Subject {role} is not release-ready'
    return field


def inventory(field, *, emitted=False):
    """Return (source-relative path, emitted-relative path) pairs; never scan all skills."""
    data = catalog()
    pairs = [('plugin.json', 'plugin.json'), (field['icon'], field['icon'])]
    reviewed = {REVIEW_FILES[s] for s in field['subjects'] if s in REVIEW_FILES}
    for role, name in field['skill_names'].items():
        entry = data['authoring'][role]
        for path in entry['files']:
            if field['number'] != '2' and role == 'exams' and Path(path).name.startswith('reviewed-'):
                if Path(path).name != 'reviewed-items.json' and Path(path).name not in reviewed:
                    continue
            pairs.append((entry['source'] + '/' + path, 'skills/' + name + '/' + path))
    return sorted(pairs, key=lambda pair: pair[1] if emitted else pair[0])
