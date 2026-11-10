"""Executable field contracts with disposable synthetic sources; no teaching/live claims."""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import package
import marketplace
import products
import stage
import validate

EXPECTED = {
    '1': {'greek', 'ancient-greek', 'history', 'latin'},
    '2': {'greek', 'mathematics', 'physics', 'chemistry'},
    '3': {'greek', 'physics', 'chemistry', 'biology'},
    '4': {'greek', 'mathematics', 'economics', 'informatics'},
}


def rejects(action, message):
    try:
        action()
    except AssertionError as error:
        assert message in str(error), f'Expected {message!r}, got {error!r}'
    else:
        raise AssertionError(f'Bad fixture accepted: {message}')
    print('PASS: rejects ' + message)


def tamper(root, field, path, transform, expected):
    path = root / path
    original = path.read_text()
    try:
        path.write_text(transform(original))
        rejects(lambda: validate.validate(root, field), expected)
    finally:
        path.write_text(original)


def update_json(text, action):
    value = json.loads(text)
    action(value)
    return json.dumps(value, ensure_ascii=False)


with tempfile.TemporaryDirectory(prefix='lyceum-product-tests-') as temporary:
    temporary = Path(temporary)
    data = products.catalog()
    for number, subjects in EXPECTED.items():
        field = products.profile(number)
        assert set(field['subjects']) == subjects
        assert len(field['skill_names']) == 6
    assert {entry['source'] for entry in data['authoring'].values()} == {
        path.parent.relative_to(ROOT).as_posix() for path in (ROOT / 'skills').glob('*/SKILL.md')
    }, 'Catalog must include every authoring Skill under the unified skills root'
    catalog_path = temporary / 'products.json'
    def bad_catalog(mutate):
        changed = copy.deepcopy(data)
        mutate(changed)
        catalog_path.write_text(json.dumps(changed))
        with patch.object(products, 'CATALOG', catalog_path):
            products.catalog()
    rejects(lambda: bad_catalog(lambda x: x['authoring']['biology'].update(source='subjects/lyceum-biology')),
            'Authoring sources must use the skills root')
    # Readiness negatives are explicit fixtures, independent of production readiness.
    for number in EXPECTED:
        changed = copy.deepcopy(data)
        changed['fields'][number]['release_ready'] = False
        catalog_path.write_text(json.dumps(changed))
        blocked = temporary / ('blocked-' + number)
        with patch.object(products, 'CATALOG', catalog_path):
            rejects(lambda n=number: package.build(n, blocked), 'not release-ready')
            rejects(lambda n=number: package.build_download_bundle(n, blocked), 'not release-ready')
            assert not blocked.exists()
            if any(value['release_ready'] for value in changed['fields'].values()):
                with contextlib.redirect_stdout(io.StringIO()):
                    ready_tree = package.build_marketplace(temporary / ('without-' + number))
                ready_manifest = json.loads((ready_tree / '.agents/plugins/marketplace.json').read_text())
                assert changed['fields'][number]['name'] not in {entry['name'] for entry in ready_manifest['plugins']}
            else:
                rejects(lambda: package.build_marketplace(temporary / ('without-' + number)), 'No release-ready fields')
    rejects(lambda: bad_catalog(lambda x: x['fields']['1'].pop('release_ready')), 'Missing field readiness')
    rejects(lambda: bad_catalog(lambda x: x['authoring']['biology'].pop('ready')), 'Missing subject readiness')
    def substitute_field_subjects(value):
        field = value['fields']['4']
        field['subjects'] = value['fields']['2']['subjects'][:]
        field['skill_names'] = {role: 'lyceum-f4-' + role for role in ['study', *field['subjects'], 'exams']}
        field['release_ready'] = True
    rejects(lambda: bad_catalog(substitute_field_subjects), 'Wrong subjects for scientific field')
    rejects(lambda: bad_catalog(lambda x: x['fields']['1']['skill_names'].update(study='lyceum-study')), 'field namespace')
    rejects(lambda: bad_catalog(lambda x: x['fields']['3']['skill_names'].update(study=x['fields']['1']['skill_names']['study'])), 'Duplicate emitted skill name')
    changed = copy.deepcopy(data)
    changed['fields']['3']['release_ready'] = True
    changed['authoring']['biology']['ready'] = False
    catalog_path.write_text(json.dumps(changed))
    with patch.object(products, 'CATALOG', catalog_path):
        rejects(lambda: products.profile('3', release=True), 'Subject biology is not release-ready')
        rejects(lambda: package.build_download_bundle('3', temporary / 'blocked-subject'), 'Subject biology is not release-ready')
        assert not (temporary / 'blocked-subject').exists()

    # Synthetic authoring lives only in this temporary tree. The production profile
    # still lists each real file explicitly; readiness is tested separately.
    fixture = temporary / 'authoring'
    fixture.mkdir()
    shutil.copyfile(ROOT / 'plugin.json', fixture / 'plugin.json')
    shutil.copytree(ROOT / 'skills', fixture / 'skills')
    shutil.copytree(ROOT / 'assets', fixture / 'assets')
    for subject in set.union(*EXPECTED.values()) - products.LEGACY_SUBJECTS:
        folder = fixture / data['authoring'][subject]['source']
        for relative in data['authoring'][subject]['files']:
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative == 'SKILL.md':
                text = (f'---\nname: lyceum-{subject}\ndescription: "Συνθετικό δείγμα ελέγχου κατασκευής"\n---\n'
                        '[Κοινή πολιτική](../lyceum-study/references/shared/teaching-policy.md)\n'
                        '[Χάρτης](references/syllabus-2027.md)\n[Πηγές](references/sources.json)\n')
            elif relative.endswith('.yaml'):
                text = f'interface:\n  display_name: "Δοκιμή"\n  short_description: "Συνθετική δοκιμή"\n  default_prompt: "$lyceum-{subject}"\n'
            elif relative.endswith('.json'):
                registry = {'subject': subject, 'exam_year': 2027, 'sources': [
                    {'id': 'SYNTHETIC-' + subject, 'url': 'https://example.org/source', 'distribution': 'link-only'}]}
                if subject == 'biology':
                    common = json.loads((ROOT / 'skills/lyceum-study/references/shared/sources.json').read_text())['sources']
                    for shared_id in ('S1', 'E1'):
                        original = next(source for source in common if source['id'] == shared_id)
                        registry['sources'].append({
                            'id': 'SYNTHETIC-ALIAS-' + shared_id,
                            'url': original['url'], 'sha256': original['sha256'],
                            'distribution': 'reference-existing-bundled-administrative-record',
                            'shared_source_id': shared_id,
                            'shared_resource': '../../lyceum-study/references/shared/' + original['file'],
                        })
                if subject == 'biology':
                    registry['sources'].append({
                        'id': 'SYNTHETIC-PAPER-biology', 'title': 'Συνθετικό δείγμα φυλλαδίου',
                        'url': 'https://www.minedu.gov.gr/synthetic-test.pdf',
                        'distribution': 'link-only', 'source_type': 'official-exam-paper',
                        'exam_year': 2026, 'page_count': 2, 'sha256': '0' * 64,
                    })
                    registry['selected_past_items'] = [{
                        'id': 'synthetic-biology-2026-A1', 'source_id': 'SYNTHETIC-PAPER-biology',
                        'year': 2026, 'item': 'A1', 'pdf_page': 1, 'official_points': 5,
                        'map_sections': ['Συνθετική ενότητα'],
                        'compatibility_rationale': 'Συνθετική αντιστοίχιση μόνο για δομικό έλεγχο.',
                        'requires_source_access': True, 'required_source_pdf_pages': [1, 2],
                        'marks_provenance': 'Συνθετικός εντοπιστής μονάδων.',
                        'required_source_parts': [
                            {'pdf_pages': [1], 'locator': 'Συνθετικός εντοπιστής ερωτήματος'},
                            {'pdf_pages': [2], 'locator': 'Συνθετικός εντοπιστής γενικών οδηγιών'},
                        ],
                    }]
                text = json.dumps(registry)
            else:
                text = '# Συνθετικό δείγμα\nΜόνο για δομικό έλεγχο, χωρίς ισχυρισμό διδακτικής κάλυψης.\n'
            target.write_text(text)
    roots = {}
    with patch.object(stage, 'ROOT', fixture):
        for number in ('1', '2', '3', '4'):
            field = products.profile(number)
            root = temporary / ('field-' + number)
            payload = stage.stage(field, root)
            with contextlib.redirect_stdout(io.StringIO()):
                manifest, files = validate.validate(root, field)
            assert manifest == json.loads(payload['plugin.json'])
            assert {path.relative_to(root).as_posix(): path.read_bytes() for path in files} == payload
            roots[number] = root
            assert len(list((root / 'skills').glob('*/SKILL.md'))) == 6
            source_policy = ROOT / 'skills/lyceum-study/references/shared/teaching-policy.md'
            assert (root / 'skills' / field['skill_names']['study'] / 'references/shared/teaching-policy.md').read_bytes() == source_policy.read_bytes()
            if number == '2':
                for source, emitted in products.inventory(field):
                    assert payload[emitted] == (ROOT / source).read_bytes()
            else:
                shared = root / 'skills' / field['skill_names']['study'] / 'references/shared'
                books = json.loads((shared / 'textbooks/catalog.json').read_text())['books']
                assert {b['subject'] for b in books} == EXPECTED[number] & products.LEGACY_SUBJECTS
                text = (root / 'skills' / field['skill_names']['study'] / 'SKILL.md').read_text()
                for role in EXPECTED[number]:
                    assert field['skill_names'][role] + '/SKILL.md' in text
                for role in set.union(*EXPECTED.values()) - EXPECTED[number]:
                    assert 'lyceum-' + role + '/SKILL.md' not in text
                exam_prompt = (root / 'skills' / field['skill_names']['exams'] / 'agents/openai.yaml').read_text()
                if 'mathematics' not in EXPECTED[number]:
                    assert 'Μαθηματικά' not in exam_prompt
                registry = json.loads((shared / 'sources.json').read_text())
                for source in registry['sources']:
                    if source['id'] in {'S1', 'S1-FEK', 'S1-NOTICE'}:
                        assert 'four target subject' not in source['status'] and 'all four subject' not in source['status']
                        assert '18-10-2026' in source['status']
            print(f'PASS: field {number}: six independent names; selected maps, catalogs, routing; policy bytes')

    field = products.profile('1')
    root = roots['1']
    names = field['skill_names']
    study = f"skills/{names['study']}"
    exam = f"skills/{names['exams']}/references"
    tamper(root, field, study + '/references/study-card.md',
           lambda t: t + '\n[escape](../../../plugin.json)\n', 'Skill reader cannot expose plugin-root link')
    tamper(root, field, study + '/references/study-card.md',
           lambda t: t + '\n[missing](absent.md)\n', 'missing/unpackaged link')
    card_path = root / study / 'references/study-card.md'
    card_original = card_path.read_text()
    try:
        card_path.write_text(card_original + '\n[remote](<https://example.org/path(with-parentheses)>)\n[local](<shared/curriculum-status.md>)\n')
        with contextlib.redirect_stdout(io.StringIO()):
            validate.validate(root, field)
    finally:
        card_path.write_text(card_original)
    print('PASS: valid angle-bracket remote and packaged local Markdown destinations')
    tamper(root, field, study + '/references/study-card.md',
           lambda t: t + '\n[escape](<../../../plugin.json>)\n', 'Skill reader cannot expose plugin-root link')
    tamper(root, field, study + '/references/study-card.md',
           lambda t: t + '\n[missing](<absent.md>)\n', 'missing/unpackaged link')
    tamper(root, field, study + '/references/shared/textbooks/catalog.json',
           lambda t: update_json(t, lambda x: x['books'][0].update(subject='physics')), 'Foreign or missing textbook subject')
    tamper(root, field, study + '/agents/openai.yaml',
           lambda t: t + '\ndependencies: {tools: [local-executor]}\n', 'Runtime execution dependencies')
    tamper(root, field, study + '/agents/openai.yaml',
           lambda t: t.replace(names['study'], 'lyceum-study'), 'unnamespaced or foreign skill reference')
    tamper(root, field, study + '/SKILL.md',
           lambda t: t.replace('name: ' + names['study'], 'name: wrong-name'), 'SKILL.md')
    tamper(root, field, 'plugin.json',
           lambda t: update_json(t, lambda value: value['extensions']['com.openai']['interface'].update(displayName='Wrong field')), 'Runtime field display name mismatch')
    tamper(root, field, 'plugin.json',
           lambda t: update_json(t, lambda value: value['extensions']['com.openai']['interface'].update(logo='../foreign.png')), 'Wrong field icon reference')
    icon = root / field['icon']
    original_icon = icon.read_bytes()
    icon.write_bytes((roots['2'] / products.profile('2')['icon']).read_bytes())
    rejects(lambda: validate.validate(root, field), 'Wrong field icon bytes')
    icon.write_bytes(original_icon)
    try:
        oversized = original_icon + bytes(128 * 1024)
        icon.write_bytes(oversized)
        rejects(lambda: validate.validate(root, field), 'Invalid icon file size')
        wrong_dimensions = bytearray(original_icon)
        wrong_dimensions[16:20] = (512).to_bytes(4, 'big')
        icon.write_bytes(wrong_dimensions)
        rejects(lambda: validate.validate(root, field), 'Invalid icon dimensions')
    finally:
        icon.write_bytes(original_icon)
    tamper(root, field, 'plugin.json',
           lambda t: update_json(t, lambda x: x.update(mcpServers={'local': {'command': 'python'}})), 'Runtime execution dependencies')
    tamper(root, field, 'plugin.json',
           lambda t: update_json(t, lambda x: x.update(desktopOnly=True)), 'Unsupported runtime manifest key')
    tamper(root, field, exam + '/reviewed-greek.json',
           lambda t: update_json(t, lambda x: x['items'][0].update(answer='α')), 'Exam records contain locators only')
    injected = root / study / 'references/foreign-physics.md'
    injected.write_text('Ανεπιθύμητο ξένο περιεχόμενο')
    rejects(lambda: validate.validate(root, field), 'unselected or missing files')
    injected.unlink()

    # Aliases identify existing originals; they cannot admit another binary or
    # weaken subject/year identity. Both S1 and E1 were exercised by the valid build.
    biology_field = products.profile('3')
    biology_root = roots['3']
    biology_registry = 'skills/lyceum-f3-biology/references/sources.json'
    def alias_change(text, **changes):
        return update_json(text, lambda value: value['sources'][1].update(changes))
    tamper(biology_root, biology_field, biology_registry,
           lambda t: alias_change(t, sha256='0' * 64), 'Administrative alias hash mismatch')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: alias_change(t, shared_source_id='NOT-REGISTERED'), 'Unregistered administrative alias')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: alias_change(t, shared_source_id='G2'), 'Alias target is not an approved administrative original')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: alias_change(t, shared_resource='../../../../../../outside.pdf'), 'Administrative alias path mismatch')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: update_json(t, lambda value: value.update(exam_year=2026)), 'Wrong subject exam year')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: update_json(t, lambda value: value.update(subject='history')), 'Wrong subject source registry')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: update_json(t, lambda value: value['sources'][0].update(distribution='bundled-administrative-record')), 'Unapproved subject source distribution')
    unapproved = biology_root / 'unapproved-copy.pdf'
    approved = biology_root / 'skills/lyceum-f3-study/references/shared/official/syllabus-2027.pdf'
    shutil.copyfile(approved, unapproved)
    try:
        tamper(biology_root, biology_field, biology_registry,
               lambda t: alias_change(t, shared_resource='../../../unapproved-copy.pdf'), 'Administrative alias path mismatch')
    finally:
        unapproved.unlink()
    print('PASS: registered administrative aliases reuse original bytes without adding a binary')

    def selected_change(text, **changes):
        return update_json(text, lambda value: value['selected_past_items'][0].update(changes))
    tamper(biology_root, biology_field, biology_registry,
           lambda t: selected_change(t, source_id='UNKNOWN'), 'Unknown selected paper source')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: selected_change(t, year=2025), 'Selected item year does not match paper')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: selected_change(t, pdf_page=3), 'Selected paper page outside source')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: selected_change(t, requires_source_access=False), 'Selected item requires source access')
    for forbidden in ('question','answer','hint','data'):
        tamper(biology_root, biology_field, biology_registry,
               lambda t, key=forbidden: selected_change(t, **{key:'α'}), 'Selected items contain locators only')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: selected_change(t, required_source_pdf_pages=[1]), 'Dependency page missing from required source pages')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: selected_change(t, required_source_parts=[{'pdf_pages': [1], 'locator': 'Θέμα Α', 'hint': 'Υπόδειξη'}]), 'Selected dependency contains locators only')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: update_json(t, lambda value: value['sources'][-1].update(source_type='textbook')), 'Selected source is not an official paper')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: update_json(t, lambda value: value['sources'][-1].update(answer='α')), 'Selected paper source contains metadata only')
    tamper(biology_root, biology_field, biology_registry,
           lambda t: update_json(t, lambda value: value.update(selected_items=[])), 'Use selected_past_items')
    print('PASS: selected-item year, source, marks, pages and dependency locators are metadata only')

    # Observe real ZIP serialization and the independently usable marketplace tree.
    first, second = temporary / 'first', temporary / 'second'
    # Serialization exercises the legacy desktop format independently of current
    # release eligibility; only this disposable fixture admits field 2.
    serialization_catalog = copy.deepcopy(data)
    serialization_catalog['fields']['2']['release_ready'] = True
    serialization_catalog_path = temporary / 'serialization-catalog.json'
    serialization_catalog_path.write_text(json.dumps(serialization_catalog))
    with contextlib.redirect_stdout(io.StringIO()):
        with patch.object(products, 'CATALOG', serialization_catalog_path):
            archive1 = package.build('2', first)
            archive2 = package.build('2', second)
        tree = package.build_marketplace(temporary / 'marketplace')
    assert archive1.read_bytes() == archive2.read_bytes()
    assert archive1.with_name(archive1.stem + '-desktop.zip').read_bytes() == archive2.with_name(archive2.stem + '-desktop.zip').read_bytes()
    with zipfile.ZipFile(archive1) as archive:
        assert not any('/scripts/' in n or '/tests/' in n or '/subjects/' in n for n in archive.namelist())
    manifest = json.loads((tree / '.agents/plugins/marketplace.json').read_text())
    ready_fields = [products.profile(number, release=True) for number, value in data['fields'].items() if value['release_ready']]
    assert manifest['plugins'] == [package.marketplace_entry(field) for field in ready_fields]
    for field in ready_fields:
        plugin = tree / 'plugins' / field['name']
        with contextlib.redirect_stdout(io.StringIO()):
            validate.validate(plugin, field)
    assert not list(tree.rglob('*.zip'))
    print('PASS: deterministic legacy runtime/desktop ZIP bytes; closed marketplace with every ready field')

    published = temporary / 'published'
    with contextlib.redirect_stdout(io.StringIO()):
        marketplace.sync(published)
        marketplace.sync(published, check=True)
        catalog_path = published / '.agents/plugins/marketplace.json'
        catalog_original = catalog_path.read_bytes()
        changed = json.loads(catalog_original)
        changed['plugins'][0]['source']['path'] = './'
        catalog_path.write_text(json.dumps(changed))
        rejects(lambda: marketplace.sync(published, check=True), 'Marketplace out of sync')
        catalog_path.write_bytes(catalog_original)
        plugin = published / manifest['plugins'][0]['source']['path']
        skill = next(plugin.glob('skills/*/SKILL.md'))
        skill_original = skill.read_bytes()
        skill.write_text('Stale published instructions')
        rejects(lambda: marketplace.sync(published, check=True), 'Marketplace out of sync')
        skill.write_bytes(skill_original)
        (plugin / 'unregistered.pdf').write_bytes(b'Synthetic unregistered content')
        rejects(lambda: marketplace.sync(published, check=True), 'Marketplace out of sync')
        marketplace.sync(published)
        marketplace.sync(published, check=True)
    assert not (plugin / 'unregistered.pdf').exists()
    print('PASS: published marketplace rejects wrong routing, stale instructions and extra material; sync restores it')

    # Exercise all four real runtimes, even when testing an unready source checkout.
    ready_catalog = copy.deepcopy(data)
    for value in ready_catalog['fields'].values():
        value['release_ready'] = True
    for value in ready_catalog['authoring'].values():
        value['ready'] = True
    catalog_path.write_text(json.dumps(ready_catalog))
    with patch.object(products, 'CATALOG', catalog_path):
        for number in EXPECTED:
            field = products.profile(number, release=True)
            with contextlib.redirect_stdout(io.StringIO()):
                bundle1 = package.build_download_bundle(number, temporary / ('download-a-' + number))
                bundle2 = package.build_download_bundle(number, temporary / ('download-b-' + number))
                runtime = package.checked_runtime(field, temporary / ('expected-runtime-' + number))
            assert bundle1.name == f"panelladikes-field-{number}-{field['version']}.zip"
            assert bundle1.read_bytes() == bundle2.read_bytes()
            assert {path.name for path in bundle1.parent.iterdir()} == {bundle1.name, bundle1.name + '.sha256'}
            prefix = field['name']
            with zipfile.ZipFile(bundle1) as archive:
                assert archive.testzip() is None
                members = {name.removeprefix(prefix + '/'): archive.read(name) for name in archive.namelist()}
                assert all(name.startswith(prefix + '/') for name in archive.namelist())
                assert len(members) == len(archive.namelist())
                assert members == package.download_payload(field, runtime)
                manifest = json.loads(members['plugin.json'])
                assert manifest['name'] == prefix
                assert manifest['version'] == field['version']
                assert manifest['extensions']['com.openai']['interface']['displayName'] == field['display_name']
                expected_names = {emitted for _, emitted in products.inventory(field)} | {'LICENSE', 'THIRD_PARTY_NOTICES.md'}
                assert set(runtime) == expected_names
                assert {name: members[name] for name in expected_names} == runtime
                assert set(members) == expected_names | {'README.md', 'USAGE.md'}
                assert not any(Path(name).parts[0] in {'plugins', '.agents', 'scripts', 'tests', 'subjects', 'docs'} for name in members)
                assert not any('candidate' in name or name.endswith('.zip') for name in members)
                assert 'desktopOnly' not in manifest
                if number == '1':
                    history = 'skills/lyceum-f1-history/references/'
                    sources = json.loads(members[history + 'sources.json'])['sources']
                    book = next(source for source in sources if source['id'] == 'H-B1')
                    fallback = book['html_fallback']
                    assert fallback['url'] == 'https://ebooks.edu.gr/ebooks/v/html/8547/2758/Themata-Neoellinikis-Istorias_G-Lykeiou_html-apli/index1_3.html'
                    assert fallback['distribution'] == 'link-only'
                    assert fallback['locator']['corresponding_printed_page'] == 18
                    assert 'before requesting a student excerpt' in fallback['retrieval']
                    assert 'not visual inspection' in fallback['limits'] and 'not presumed to include every V2 correction' in fallback['limits']
                    assert fallback['url'] in members[history + 'book-navigation.md'].decode()
                unpacked = temporary / ('unpacked-' + number)
                archive.extractall(unpacked)
            with contextlib.redirect_stdout(io.StringIO()):
                validate.validate(unpacked / prefix, field)
            print(f'PASS: field {number} deterministic uploadable single-plugin ZIP; exact portable runtime and no marketplace wrapper')
