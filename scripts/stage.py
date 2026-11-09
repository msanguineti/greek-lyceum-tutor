"""Compile one explicit product into a self-contained, private staging directory."""
import json
import re
from pathlib import Path
from products import ROOT, catalog, inventory, LEGACY_SUBJECTS, REVIEW_FILES


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def rename_skills(text, field):
    names = {'lyceum-' + role: name for role, name in field['skill_names'].items()}
    return re.sub(r'(?<![\w-])lyceum-[a-z-]+(?![\w-])',
                  lambda match: names.get(match.group(), match.group()), text)


def routing(field, *, maps=False, prefix='../'):
    data = catalog()['authoring']
    tail = 'references/syllabus-2027.md' if maps else 'SKILL.md'
    return ', '.join(f"[{data[s]['label']}]({prefix}{field['skill_names'][s]}/{tail})"
                     for s in field['subjects'])


def subject_metadata(node, subjects):
    """Filter subject-keyed sections in shared administrative metadata."""
    aliases = {'math': 'mathematics', **{s: s for s in catalog()['authoring']}}
    if isinstance(node, dict):
        return {k: subject_metadata(v, subjects) for k, v in node.items()
                if k not in aliases or aliases[k] in subjects}
    if isinstance(node, list):
        return [subject_metadata(v, subjects) for v in node]
    return node


def compile_shared(payload, field):
    """Specialize routing/catalogs; keep the shared teaching policy byte-identical."""
    names = field['skill_names']
    study = f"skills/{names['study']}"
    exams = f"skills/{names['exams']}/references"
    shared = f'{study}/references/shared'
    data = catalog()
    label = ', '.join(data['authoring'][s]['label'] for s in field['subjects'])
    study_entry = payload[f'{study}/SKILL.md'].decode()
    lines = []
    for line in study_entry.splitlines():
        if line.startswith('Αν προχωράς σε διδασκαλία,'):
            line = ('Αν προχωράς σε διδασκαλία, διάβασε το αντίστοιχο Skill και τις υποχρεωτικές αναφορές του: '
                    + routing(field) + f". Για δοκιμασία διάβασε την [εξάσκηση](../{names['exams']}/SKILL.md). "
                    'Η ανάγνωση οδηγιών δεν συνεπάγεται αυτόματη μεταφορά σε άλλο agent.')
        if line.startswith('Για αίτημα διδασκαλίας άλλου μαθήματος'):
            line = ('Για αίτημα διδασκαλίας μαθήματος εκτός του παραπάνω καταλόγου, εξήγησε τα όρια '
                    'αυτού του tutor και πρόσφερε επιστροφή σε υποστηριζόμενο στόχο. '
                    'Μην υπόσχεσαι ελεγμένη διδασκαλία εκτός πεδίου.')
        lines.append(line)
    payload[f'{study}/SKILL.md'] = ('\n'.join(lines) + '\n').encode()
    exam_entry = payload[f"skills/{names['exams']}/SKILL.md"].decode()
    exam_entry = re.sub(r'^Φόρτωσε το αντίστοιχο subject Skill.*$',
        'Φόρτωσε το αντίστοιχο subject Skill και τον χάρτη του: ' + routing(field) +
        '. Έλεγξε κάθε ζητούμενο και μέθοδο ως προς τον χάρτη 2027 και τις εξαιρέσεις του.',
        exam_entry, flags=re.M)
    new_subjects = [s for s in field['subjects'] if s not in LEGACY_SUBJECTS]
    selected_links = ', '.join(
        f"[{data['authoring'][s]['label']}](../../{names[s]}/references/sources.json)"
        for s in new_subjects)
    entry_selected_links = selected_links.replace('](../../', '](../')
    exam_entry += ('\nΓια τα νέα μαθήματα, οι ελεγμένοι εντοπιστές παλαιών ερωτημάτων βρίσκονται '
                   'στο `selected_past_items` του ιδιαίτερου μητρώου: ' + entry_selected_links + '. '
                   'Διάβασε τις απαιτούμενες σελίδες και οδηγίες από την πραγματική επίσημη πηγή. '
                   'Οι εντοπιστές δεν περιέχουν εκφώνηση ή λύση και δεν εγκρίνουν τα υπόλοιπα ερωτήματα του φυλλαδίου.\n')
    payload[f"skills/{names['exams']}/SKILL.md"] = exam_entry.encode()
    exam_yaml = f"skills/{names['exams']}/agents/openai.yaml"
    prompt = ('Χρησιμοποίησε το $' + names['exams'] +
              ' για σύντομη ανεξάρτητη εξάσκηση σε μάθημα αυτού του πεδίου και διόρθωση μετά την προσπάθειά μου.')
    payload[exam_yaml] = re.sub(r'^  default_prompt:.*$',
        '  default_prompt: ' + json.dumps(prompt, ensure_ascii=False),
        payload[exam_yaml].decode(), flags=re.M).encode()
    card = f'{study}/references/study-card.md'
    payload[card] = payload[card].decode().replace(
        'Η λέξη «όρια» μόνη της δεν τεκμηριώνει την §1.5.',
        'Μια γενική λέξη-κλειδί μόνη της δεν τεκμηριώνει συγκεκριμένη ενότητα.').encode()
    payload[f'{shared}/curriculum-status.md'] = (
        f"# Ύλη και κατάσταση έκδοσης\nΣτόχος: Γ΄ ΓΕΛ, {field['number']}ο Επιστημονικό Πεδίο, Πανελλαδικές 2027.\n"
        f"Η έκδοση {field['version']} περιλαμβάνει έξι Skills: μελέτη, {label}, εξάσκηση/προσομοιώσεις.\n"
        'Το τοπικό υποψήφιο περιεχόμενο δεν αποτελεί απόδειξη εγκατάστασης ή ανεξάρτητης αποδοχής.\n'
        'Πριν διδάξεις διάβασε τον σχετικό χάρτη και τις ρητές εξαιρέσεις:\n' +
        '\n'.join('- ' + routing(dict(field, subjects=[s]), maps=True, prefix='../../../')
                  for s in field['subjects']) + '\n' +
        f"- [Τρόπος εξέτασης](../../../{names['exams']}/references/exam-rules.md)\n"
        'Άγνωστη ύλη δεν χαρακτηρίζεται εντός ύλης. Νεότερη επίσημη απόφαση χρειάζεται έλεγχο και νέα έκδοση. '
        'Οι εξεταστικές πηγές διαφέρουν από τις διδακτικές οδηγίες και την ύλη απολυτηρίων. '
        'Τα προαπαιτούμενα δηλώνονται ως υποστήριξη συγκεκριμένου εντός ύλης στόχου.\n'
        'Το [μητρώο κοινών πηγών](sources.json) και τα ιδιαίτερα μητρώα των μαθημάτων κρατούν την προέλευση. '
        'Βιβλία, παλαιά θέματα και πλήρεις οδηγίες ΙΕΠ είναι μόνο επίσημοι σύνδεσμοι. '
        'Για συγκεκριμένη εκφώνηση χρειάζεται πραγματική πρόσβαση σε όλο το αναγκαίο περιεχόμενο.\n'
        '[Όρια ελέγχου](curriculum-audit-2026-10-18.md). Δεν υπάρχει αυτόματη ενημέρωση ύλης ή αποθήκευση προόδου.\n'
    ).encode()
    inherited = [s for s in field['subjects'] if s in LEGACY_SUBJECTS]
    payload[f'{shared}/curriculum-audit-2026-10-18.md'] = (
        '# Προέλευση και όρια ελέγχου\n'
        'Το όνομα του αρχείου διατηρεί τις παραπομπές των επαναχρησιμοποιούμενων χαρτών. '
        'Ο αρχικός έλεγχος της 18-10-2026 αφορά μόνο τα επαναχρησιμοποιούμενα μαθήματα: '
        + ', '.join(data['authoring'][s]['label'] for s in inherited) + '. '
        'Δεν μεταφέρει την ίδια ημερομηνία ή αποδοχή στα νέα μαθήματα.\n'
        'Διάβασε τον συγκεκριμένο χάρτη, την προέλευση, τις ημερομηνίες και τα όρια ελέγχου κάθε μαθήματος: '
        + routing(field, maps=True, prefix='../../../') + '.\n'
        'Οι έξι διοικητικές πρωτογενείς πηγές διατηρούνται αμετάβλητες. '
        'Η παρουσία τους δεν αποδεικνύει πλήρη έλεγχο όλων των μαθημάτων, μεταγενέστερων αλλαγών ή πραγματικής λειτουργίας ChatGPT. '
        'Οι χάρτες και οι ρητές εξαιρέσεις ελέγχουν την εξετασιμότητα. '
        'Όταν προκύπτει ασυνέπεια οδηγιών, διάβασε τα ειδικά όρια του αντίστοιχου χάρτη.\n'
        '[Κοινές πηγές](sources.json).\n'
    ).encode()
    books = json.loads(payload[f'{shared}/textbooks/catalog.json'])
    books['books'] = [b for b in books['books'] if b['subject'] in field['subjects']]
    payload[f'{shared}/textbooks/catalog.json'] = json_bytes(books)
    reviewed = json.loads(payload[f'{exams}/reviewed-items.json'])
    allowed_reviewed = {REVIEW_FILES[s] for s in inherited}
    reviewed['subjects'] = [g for g in reviewed['subjects'] if g['file'] in allowed_reviewed]
    reviewed['scope'] = ('Το παρόν ευρετήριο καλύπτει μόνο τα επαναχρησιμοποιούμενα μαθήματα. '
                         'Για τα νέα μαθήματα, διάβασε το selected_past_items στο ιδιαίτερο μητρώο πηγών '
                         'που συνδέεται από το Skill εξάσκησης. Καμία καταχώριση δεν εγκρίνει ολόκληρο φυλλάδιο.')
    payload[f'{exams}/reviewed-items.json'] = json_bytes(reviewed)
    paper_ids = set()
    for group in reviewed['subjects']:
        for item in json.loads(payload[f"{exams}/{group['file']}"])['items']:
            paper_ids.add(item['source_id'])
    papers = json.loads(payload[f'{exams}/past-papers.json'])
    papers['papers'] = [p for p in papers['papers'] if p['source_id'] in paper_ids]
    payload[f'{exams}/past-papers.json'] = json_bytes(papers)
    sources = json.loads(payload[f'{shared}/sources.json'])
    source_ids = set(data['common_source_ids']) | paper_ids
    for subject in field['subjects']:
        source_ids.update(data['authoring'][subject].get('source_ids', []))
    sources['sources'] = [subject_metadata(s, field['subjects']) for s in sources['sources'] if s['id'] in source_ids]
    for source in sources['sources']:
        if source['id'] in {'S1', 'S1-FEK', 'S1-NOTICE'}:
            source['status'] = ('Επίσημο διοικητικό πρωτότυπο με διατηρημένη ταυτότητα και αποτύπωμα. '
                'Ο αρχικός έλεγχος 18-10-2026 αφορά μόνο τα επαναχρησιμοποιούμενα μαθήματα: ' +
                ', '.join(data['authoring'][s]['label'] for s in inherited) + '. '
                'Για τα νέα μαθήματα διάβασε τους ιδιαίτερους χάρτες, την προέλευση και τα όρια ελέγχου τους.')
    if 'mathematics' not in field['subjects']:
        for source in sources['sources']:
            source.pop('math_pages', None)
    sources['limitations'] = ['Το κοινό μητρώο περιλαμβάνει μόνο πηγές των επιλεγμένων μαθημάτων και τις έξι κοινές διοικητικές πηγές. Η αναλυτική επαλήθευση παραμένει στους χάρτες και στα ιδιαίτερα μητρώα μαθημάτων. Δεν υπάρχει αυτόματη ενημέρωση ή τεκμήριο πλήρους αποδοχής.']
    payload[f'{shared}/sources.json'] = json_bytes(sources)
    historical = payload[f'{exams}/historical-selection.md'].decode()
    allowed_labels = [data['authoring'][s]['label'].split()[0] for s in inherited]
    historical = '\n'.join(line for line in historical.splitlines()
                           if not line.startswith('- ') or any(line.startswith('- ' + x) for x in allowed_labels)) + '\n'
    historical += ('\nΟι νέες επιλογές καταγράφονται χωριστά στα μητρώα μαθημάτων: ' + selected_links + '. '
                   'Διάβασε το `selected_past_items`, την αντιστοίχιση στον χάρτη2027 και όλες τις απαιτούμενες '
                   'σελίδες/οδηγίες από την επίσημη πηγή πριν από χορήγηση ή διόρθωση. '
                   'Η συμβατότητα αφορά αποκλειστικά το επιλεγμένο ερώτημα.\n')
    payload[f'{exams}/historical-selection.md'] = historical.encode()
    # Reuse verified format descriptions only for inherited subjects. New-subject formats
    # must come from that subject's actual inspected sources before a full simulation.
    original_rules = payload[f'{exams}/exam-rules.md'].decode()
    sections = dict(re.findall(r'^## ([^\n]+)\n(.*?)(?=^## |\Z)', original_rules, re.M | re.S))
    rules = ('# Τρόπος εξέτασης και όρια επαλήθευσης\n'
             f"Στόχος: {field['number']}ο Πεδίο, Γ΄ ΓΕΛ, Πανελλαδικές 2027.\n"
             'Η διάρκεια τριών ωρών ανά μάθημα ΓΕΛ τεκμηριώνεται στην κοινή πηγή P1. '
             'Οι παρακάτω περιγραφές επαναχρησιμοποιούνται από τον έλεγχο 18-10-2026 μόνο για τα μαθήματα που κατονομάζουν. '
             'Δεν τεκμαίρεται εξαντλητικός έλεγχος μεταγενέστερων τροποποιήσεων. '
             'Οι μονάδες πραγματικού παλαιού θέματος ακολουθούν την επαληθευμένη εκφώνηση. '
             'Οι πρόσθετες εκπαιδευτικές κλίμακες δεν είναι επίσημη βαθμολόγηση.\n\n')
    rules += '## Νεοελληνική Γλώσσα και Λογοτεχνία\n' + sections['Νεοελληνική Γλώσσα και Λογοτεχνία']
    if 'mathematics' in field['subjects']:
        rules += '## Μαθηματικά Προσανατολισμού\n' + sections['Μαθηματικά Προσανατολισμού']
    if {'physics', 'chemistry'}.issubset(field['subjects']):
        rules += '## Φυσική και Χημεία Προσανατολισμού\n' + sections['Φυσική και Χημεία Προσανατολισμού']
    rules += ('\n## Άλλα μαθήματα του πεδίου\n'
              'Για μάθημα χωρίς ειδική περιγραφή παραπάνω, διάβασε τον δικό του χάρτη και μητρώο πηγών. '
              'Μη μεταφέρεις δομή, μονάδες ή κανόνες άλλου μαθήματος. '
              'Πλήρης προσομοίωση απαιτεί πρώτα πραγματική επαλήθευση της ισχύουσας μορφής και επιτρεπόμενης ύλης. '
              'Αν λείπει η τεκμηρίωση, πρότεινε σαφώς πρωτότυπη θεματική εξάσκηση και δήλωσε το συγκεκριμένο κενό.\n'
              '[Χάρτες](../../' + names['study'] + '/references/shared/curriculum-status.md), '
              '[κοινές πηγές](../../' + names['study'] + '/references/shared/sources.json), '
              '[πρωτόκολλο](exam-protocol.md).\n')
    payload[f'{exams}/exam-rules.md'] = rules.encode()


def stage(field, destination):
    destination = Path(destination)
    assert not destination.exists() or not any(destination.iterdir()), 'Staging destination must be empty'
    payload = {}
    for source, target in inventory(field, emitted=True):
        path = ROOT / source
        assert path.is_file() and not path.is_symlink(), f'Missing selected source: {source}'
        payload[target] = path.read_bytes()
    if field['number'] != '2':
        manifest = json.loads(payload['plugin.json'])
        manifest.update(name=field['name'], version=field['version'],
                        description=f"Greek-language tutoring for field {field['number']}, 2027 Panellinies.")
        interface = manifest['extensions']['com.openai']['interface']
        interface['displayName'] = field['display_name']
        interface['longDescription'] = ', '.join(catalog()['authoring'][s]['label'] for s in field['subjects']) + '. Μικρά βήματα, υποδείξεις, μελέτη και εξάσκηση για τις Πανελλαδικές 2027. Δεν αποθηκεύεται αυτόματα προσωπική πρόοδος.'
        manifest['extensions']['com.openai']['onboardingSkill'] = f"./skills/{field['skill_names']['study']}/SKILL.md"
        payload['plugin.json'] = json_bytes(manifest)
        compile_shared(payload, field)
        for name, content in list(payload.items()):
            if Path(name).suffix in {'.md', '.json', '.yaml'}:
                text = rename_skills(content.decode(), field)
                text = text.replace('2ου πεδίου', field['number'] + 'ου πεδίου')
                payload[name] = text.encode()
    for name, content in payload.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return payload
