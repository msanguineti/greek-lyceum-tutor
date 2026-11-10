#!/usr/bin/env python3
"""Structural/package validation; does not certify teaching behaviour."""
import hashlib, json, re, struct, sys
from pathlib import Path
import yaml
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from products import catalog, profile, inventory, LEGACY_SUBJECTS, REVIEW_FILES
SHARED=ROOT/'skills/lyceum-study/references/shared'
def markdown_link_destinations(text):
    """Accept Markdown angle-bracket destinations without relaxing local closure."""
    for destination in re.findall(r'\]\((<[^<>\n]*>|[^)\n]*)\)', text):
        if destination.startswith('<') and destination.endswith('>'):
            destination=destination[1:-1]
        yield destination

def runtime_files(root=None, field=None):
    root = ROOT if root is None else Path(root)
    field = profile() if field is None else field
    return sorted(root / dest for _, dest in inventory(field, emitted=True))

def validate(root, field=None):
    """Validate an existing runtime; returned file paths remain owned by the caller."""
    field = profile() if field is None else field
    ROOT = Path(root)
    names = field['skill_names']
    SHARED = ROOT / 'skills' / names['study'] / 'references/shared'
    assert not (ROOT/'references').exists(), 'Runtime shared sources must live inside a recognized Skill'
    m=json.loads((ROOT/'plugin.json').read_text())
    assert m['$schema']=='https://agent-plugins.org/schemas/1.0.0/plugin.schema.json'
    assert m['name']==field['name']
    assert re.fullmatch(r'\d+\.\d+\.\d+',m['version'])
    assert m['version']==field['version'], 'Runtime release version mismatch'
    assert f"Η έκδοση {m['version']} " in (SHARED/'curriculum-status.md').read_text(), 'Runtime release version mismatch'
    assert not {'skills','mcpServers','apps','interface','hooks','dependencies'} & m.keys(), 'Runtime execution dependencies are forbidden'
    assert not m.keys()-{'$schema','name','version','description','extensions'}, 'Unsupported runtime manifest key'
    assert set(m['extensions'])=={'com.openai'}, 'Unsupported runtime extension'
    ext=m['extensions']['com.openai']; interface=ext['interface']
    assert interface['displayName']==field['display_name'], 'Runtime field display name mismatch'
    assert len(interface['shortDescription'])<=30
    assert isinstance(interface['capabilities'],list)
    assert not {'apps','hooks','mcpServers','dependencies'} & ext.keys(), 'Runtime execution dependencies are forbidden'
    assert not ext.keys()-{'onboardingSkill','interface'}, 'Unsupported runtime extension key'
    assert not interface.keys()-{'displayName','shortDescription','longDescription','category','capabilities','defaultPrompt','logo','composerIcon'}, 'Unsupported runtime interface key'
    assert interface.get('logo') == interface.get('composerIcon') == './' + field['icon'], 'Wrong field icon reference'
    icon = ROOT / field['icon']
    assert icon.is_file() and not icon.is_symlink(), 'Missing field icon'
    image = icon.read_bytes()
    assert 33 <= len(image) <= 128 * 1024, 'Invalid icon file size'
    assert image[:8] == b'\x89PNG\r\n\x1a\n' and image[12:16] == b'IHDR', 'Icon must be PNG'
    width, height = struct.unpack('>II', image[16:24])
    assert width == height == 256, 'Invalid icon dimensions'
    assert hashlib.sha256(image).hexdigest() == field['icon_sha256'], 'Wrong field icon bytes'
    files=runtime_files(ROOT, field); allowed={p.resolve() for p in files}
    assert (ROOT/ext['onboardingSkill']).resolve() in allowed
    skills=list((ROOT/'skills').glob('*/SKILL.md')); assert len(skills)==6
    assert {p.parent.name for p in skills} == set(names.values()), 'Foreign or missing field skill'
    actual={p.relative_to(ROOT).as_posix() for directory in ('skills','assets') for p in (ROOT/directory).rglob('*') if p.is_file()}
    expected={p.relative_to(ROOT).as_posix() for p in files if p.name!='plugin.json'}
    assert actual==expected, 'Runtime inventory contains unselected or missing files'
    assert ext['onboardingSkill']==f"./skills/{names['study']}/SKILL.md", 'Wrong field onboarding'
    assert not list(ROOT.glob('**/hooks.json')), 'Runtime hooks are forbidden'
    for subject in field['subjects']:
        assert (ROOT/'skills'/names[subject]/'references/syllabus-2027.md').is_file(), 'Missing subject scope map'
        if subject not in LEGACY_SUBJECTS:
            provenance=json.loads((ROOT/'skills'/names[subject]/'references/sources.json').read_text())
            assert provenance.get('sources'), 'Missing subject source provenance'
    for p in files:
        assert p.is_file(), f'Missing selected runtime file: {p}'
        assert not p.is_symlink(),p
        assert not any(part.startswith('.') for part in p.relative_to(ROOT).parts),p
        assert p.resolve().is_relative_to(ROOT)
        assert p.suffix.lower() in {'.json','.md','.yaml','.pdf','.docx','.png'}, f'Runtime executables or unapproved binary: {p}'
        assert p.name=='plugin.json' or p.is_relative_to(ROOT/'skills') or p==icon, f'Unexposed plugin-root source: {p}'
        if p.suffix=='.json':
            obj=json.loads(p.read_text())
            def check_paths(node):
                if isinstance(node,dict):
                    for key,value in node.items():
                        if key in ('file','map_file','packaged_pdf','reviewed_items') and isinstance(value,str):
                            assert (p.parent/value).resolve() in allowed, f'{p}: missing runtime path {value}'
                        check_paths(value)
                elif isinstance(node,list):
                    for value in node:check_paths(value)
            check_paths(obj)
        if p.suffix=='.yaml':
            obj=yaml.safe_load(p.read_text()); assert isinstance(obj,dict),p
            assert 'dependencies' not in obj, 'Runtime execution dependencies are forbidden'
            for key in ('display_name','short_description'):assert isinstance(obj['interface'][key],str) and obj['interface'][key].strip(),p
        if p.suffix in {'.md','.yaml','.json'}:
            text=p.read_text(encoding='utf-8')
            if field['number']!='2':
                for role in catalog()['authoring']:
                    assert not re.search(r'(?<![\w-])lyceum-'+re.escape(role)+r'(?![\w-])', text), f'{p}: unnamespaced or foreign skill reference'
        if p.suffix=='.md' and not ('book-text' in p.parts and p.name!='index.md'):
            text=p.read_text(encoding='utf-8')
            assert '/home/' not in text, f'{p}: runtime document depends on developer path'
            assert not re.search(r'(?i)(?:requires?|απαιτείται|χρειάζεται) (?:a |an |το |τον )?(?:MCP|backend|local executor|desktop)',text), f'{p}: runtime environment dependency'
            for link in markdown_link_destinations(text):
                if link.startswith(('https://','http://','#')):continue
                dest=(p.parent/link.split('#')[0]).resolve()
                assert dest in allowed, f'{p}: missing/unpackaged link {link}'
                assert dest.is_relative_to(ROOT/'skills'), f'{p}: Skill reader cannot expose plugin-root link {link}'
            assert '[TODO:' not in text,p
    for p in skills:
        assert p.stat().st_size<=1024*1024
        match=re.match(r'^---\n(.*?)\n---\n',p.read_text(),re.S);assert match,p
        front=yaml.safe_load(match.group(1));assert front['name']==p.parent.name,p
        assert isinstance(front['description'],str) and front['description'].strip(),p
    sources=json.loads((SHARED/'sources.json').read_text())['sources']
    source_by_id={source['id']:source for source in sources}
    assert len(source_by_id)==len(sources), 'Duplicate source ID'
    administrative={
        'syllabus-2027.pdf', 'syllabus-2027-fek-4210.pdf',
        'syllabus-2027-publication-notice.pdf', 'exam-rules-fek-5136-2022.pdf',
        'application-2026.pdf', 'programme-2027.docx',
    }
    bundled={}
    for source in sources:
        assert source['url'].startswith('https://')
        if 'sha256' in source:assert re.fullmatch(r'[0-9a-f]{64}',source['sha256']),source['id']
        if 'file' in source:
            p=SHARED/source['file'];assert p.resolve() in allowed
            assert p.parent==SHARED/'official' and p.name in administrative, 'Unapproved bundled source'
            assert source['distribution']=='bundled-administrative-record',source['id']
            assert source['rights_url'].startswith('https://opi.gr/'),source['id']
            assert hashlib.sha256(p.read_bytes()).hexdigest()==source['sha256'],source['id']
            assert p.name not in bundled, 'Duplicate bundled source'
            bundled[p.name]=p.resolve()
        elif source.get('distribution'):
            assert source['distribution']=='link-only',source['id']
            assert source.get('snapshot_included') is not True, 'Link-only source cannot claim bundled snapshot'
    assert set(bundled)==administrative, 'Missing administrative source'
    for p in files:
        assert p.suffix.lower()!='.txt', 'Unapproved extracted full text'
        if p.suffix.lower() in {'.pdf','.docx'}:
            assert p.resolve() in bundled.values(), 'Unapproved bundled source'
    assert not list((ROOT/'skills').glob('*/references/book-text')), 'Extracted textbook indexes are not distributed'
    assert not (SHARED/'textbooks/text').exists(), 'Extracted textbook indexes are not distributed'

    book_catalog=json.loads((SHARED/'textbooks/catalog.json').read_text())
    book_ids=set()
    for book in book_catalog['books']:
        assert book['id'] not in book_ids, f"duplicate textbook: {book['id']}"
        book_ids.add(book['id'])
        assert 'file' not in book, 'Link-only source cannot include local file'
        assert book['distribution']=='link-only',book['id']
        assert re.fullmatch(r'[0-9a-f]{64}',book['sha256']),book['id']
        assert isinstance(book['page_count'],int) and book['page_count']>0,book['id']
        assert book['url'].startswith('https://') and 'ebooks.edu.gr' in book['url'],book['id']
        assert book['rights']['basis_url']=='https://ebooks.edu.gr/ebooks/',book['id']
        assert 1<=book['rights']['notice_pdf_page']<=book['page_count'],book['id']
        for pair in book['verified_page_pairs']:
            assert isinstance(pair['pdf'],int) and 1<=pair['pdf']<=book['page_count'],book['id']
    assert {b['subject'] for b in book_catalog['books']} == set(field['subjects']) & LEGACY_SUBJECTS, 'Foreign or missing textbook subject'
    for subject in field['subjects']:
        if subject not in LEGACY_SUBJECTS:
            registry=ROOT/'skills'/names[subject]/'references/sources.json'
            validate_subject_sources(registry, subject=subject, shared=SHARED,
                                     source_by_id=source_by_id, bundled=bundled, allowed=allowed)
    print(f'PASS: {len(book_ids)} link-only textbook records; attribution, source hashes and page locators')

    exam=ROOT/'skills'/names['exams']/'references'
    papers=json.loads((exam/'past-papers.json').read_text())['papers']
    reviewed_catalog=json.loads((exam/'reviewed-items.json').read_text())
    items=[]
    for group in reviewed_catalog['subjects']:
        assert group['file'] in {REVIEW_FILES[s] for s in field['subjects'] if s in REVIEW_FILES}, 'Foreign exam subject'
        detailed=json.loads((exam/group['file']).read_text())['items']
        assert {x['id'] for x in group['items']}=={x['id'] for x in detailed}
        assert all(x['requires_source_text'] is True for x in group['items'])
        items.extend(detailed)
    paper_ids={}
    for paper in papers:
        assert paper['source_id'] not in paper_ids, 'Duplicate paper source ID'
        assert 'file' not in paper, 'Link-only source cannot include local file'
        assert paper['distribution']=='link-only'
        assert paper['source_container'] in {'annual_archive','single_paper'}
        if paper['source_container']=='annual_archive':
            assert paper['sha256']==paper['archive_sha256'], 'Archive URL hash must identify archive bytes'
        source=source_by_id[paper['source_id']]
        assert source['distribution']=='link-only' and 'file' not in source
        assert paper['sha256']==source['sha256'] and paper['url']==source['url']
        paper_ids[paper['source_id']]=paper
    if field['number']!='2':
        assert set(paper_ids)=={item['source_id'] for item in items}, 'Foreign or unselected paper source'
        source_ids=set(catalog()['common_source_ids']) | set(paper_ids)
        for subject in field['subjects']:
            source_ids.update(catalog()['authoring'][subject].get('source_ids', []))
        assert set(source_by_id)==source_ids, 'Foreign or missing shared source'
    allowed_item_fields={'id','subject','year','date','exam_system','pdf','url','pdf_page','printed_page','archive_pdf_page','item','official_points','official_point_parts','map_file','map_sections','syllabus_pages','compatibility_rationale','required_text_access','required_formula_access','sha256','archive_sha256','compatibility_status','adaptation','source_id','requires_source_access','source_request','source_pdf_page','source_container','source_checked_on','reviewed_extract_sha256','source_alternatives','skills_tested','word_limit'}
    allowed_dependency_fields={'pdf_pages','source_pdf_pages','text_number','title','attribution','instructions'}
    seen=set()
    for item in items:
        assert not item.keys()-allowed_item_fields, 'Exam records contain locators only; unexpected answer/data field'
        for dep_key in ('required_text_access','required_formula_access'):
            dep=item.get(dep_key)
            if isinstance(dep,dict):
                assert not dep.keys()-allowed_dependency_fields, 'Exam dependency contains unexpected answer/data field'

        assert item['id'] not in seen, f"duplicate item: {item['id']}"
        seen.add(item['id'])
        assert not {'question','question_latex','choices','packaged_pdf'} & item.keys(), 'Copied exam prompt is not distributed'
        paper=paper_ids[item['source_id']]
        assert item['sha256']==paper['sha256'] and item['url']==paper['url'],item['id']
        assert item['requires_source_access'] is True,item['id']
        assert item['source_pdf_page']==(item['archive_pdf_page'] if item['source_container']=='annual_archive' else item['pdf_page']), 'Wrong source-container page'
        assert item['source_container']==paper['source_container'],item['id']
        for key in ('required_text_access','required_formula_access'):
            dep=item.get(key)
            if isinstance(dep,dict) and dep.get('pdf_pages'):
                offset=item['source_pdf_page']-item['pdf_page']
                assert dep['source_pdf_pages']==[offset+n for n in dep['pdf_pages']], 'Wrong dependency-container pages'
        assert isinstance(item['official_points'],(int,float)) and 0<item['official_points']<=100,item['id']
        assert isinstance(item['pdf_page'],int) and item['pdf_page']>=1,item['id']
        for key in ('source_request','url','compatibility_rationale'):
            assert isinstance(item[key],str) and item[key].strip(), (item['id'],key)
        assert item['map_sections'],item['id']
        if item.get('official_point_parts'):
            assert sum(item['official_point_parts'].values())==item['official_points'],item['id']
    print(f'PASS: {len(papers)} link-only paper sources; {len(items)} reviewed educational records')
    print(f'PASS: {len(bundled)} unchanged administrative originals; redistribution boundary')
    print(f'PASS: {len(skills)} skills; {len(files)} runtime files; metadata, links, source hashes, package boundary')
    return m,files
def validate_subject_sources(path, *, subject, shared, source_by_id, bundled, allowed):
    """New sources are link-only, or explicit aliases of an already verified original."""
    registry=json.loads(path.read_text())
    assert registry.get('subject')==subject, 'Wrong subject source registry'
    assert registry.get('exam_year')==2027, 'Wrong subject exam year'
    sources=registry['sources']
    assert sources and len({s['id'] for s in sources})==len(sources), 'Missing/duplicate subject sources'
    for source in sources:
        assert source['url'].startswith('https://'), source['id']
        assert 'file' not in source and 'packaged_pdf' not in source, 'Unapproved bundled source'
        distribution=source.get('distribution')
        if distribution=='reference-existing-bundled-administrative-record':
            shared_id=source.get('shared_source_id')
            assert shared_id in source_by_id, 'Unregistered administrative alias'
            original=source_by_id[shared_id]
            assert original.get('distribution')=='bundled-administrative-record' and 'file' in original, 'Alias target is not an approved administrative original'
            target=(shared/original['file']).resolve()
            assert target in bundled.values() and target in allowed, 'Alias target is not an approved administrative original'
            reference=source.get('shared_resource')
            assert isinstance(reference,str) and reference and not Path(reference).is_absolute(), 'Administrative alias path mismatch'
            assert (path.parent/reference).resolve()==target, 'Administrative alias path mismatch'
            assert source.get('sha256')==original['sha256']==hashlib.sha256(target.read_bytes()).hexdigest(), 'Administrative alias hash mismatch'
        else:
            assert distribution=='link-only', 'Unapproved subject source distribution'
            assert not {'shared_source_id','shared_resource'} & source.keys(), 'Administrative alias metadata requires explicit distribution'
        assert source.get('snapshot_included') is not True, 'Link-only source cannot claim bundled snapshot'
        if source.get('sha256'):
            assert re.fullmatch(r'[0-9a-f]{64}',source['sha256']),source['id']
    validate_selected_past_items(registry)


def validate_selected_past_items(registry):
    """Past items retain retrieval metadata, never question data or answer material."""
    assert 'selected_items' not in registry, 'Use selected_past_items for selected paper metadata'
    items=registry.get('selected_past_items', [])
    assert isinstance(items,list), 'Selected paper items must be a list'
    sources={source['id']:source for source in registry['sources']}
    required={'id','source_id','year','item','pdf_page','official_points','map_sections',
              'compatibility_rationale','requires_source_access','required_source_pdf_pages'}
    optional={'marks_provenance','required_source_parts'}
    paper_fields={'id','title','url','sha256','source_type','exam_year','page_count',
                  'distribution','snapshot_included','verified_on','source_checked_on',
                  'exam_date','edition','bytes','reviewed_parts','status','limits','hash_scope'}
    seen=set()
    for item in items:
        assert isinstance(item,dict) and not item.keys()-(required|optional), 'Selected items contain locators only'
        assert required <= item.keys(), 'Missing required selected-item metadata'
        for key in ('id','source_id','item','compatibility_rationale'):
            assert isinstance(item[key],str) and item[key].strip(), 'Missing required selected-item metadata'
        assert item['id'] not in seen, 'Duplicate selected-item ID'
        seen.add(item['id'])
        assert item['source_id'] in sources, 'Unknown selected paper source'
        source=sources[item['source_id']]
        assert source.get('source_type')=='official-exam-paper', 'Selected source is not an official paper'
        assert not source.keys()-paper_fields, 'Selected paper source contains metadata only'
        assert source.get('distribution')=='link-only', 'Selected source is not a link-only paper'
        host=urlsplit(source['url']).hostname or ''
        assert host=='minedu.gov.gr' or host.endswith('.minedu.gov.gr'), 'Selected paper requires an official Ministry URL'
        assert isinstance(source.get('sha256'),str) and re.fullmatch(r'[0-9a-f]{64}',source['sha256']), 'Selected paper requires source hash'
        assert type(source.get('exam_year')) is int and 1900<=source['exam_year']<registry['exam_year'], 'Invalid selected paper year'
        assert type(item['year']) is int and item['year']==source['exam_year'], 'Selected item year does not match paper'
        if 'page_count' in source:
            assert type(source['page_count']) is int and source['page_count']>0, 'Invalid selected paper page count'
        def check_page(page):
            assert type(page) is int and page>=1, 'Invalid selected paper page'
            if 'page_count' in source:
                assert page<=source['page_count'], 'Selected paper page outside source'
        def check_pages(pages):
            assert isinstance(pages,list) and pages, 'Missing selected paper pages'
            for page in pages:
                check_page(page)
            assert len(pages)==len(set(pages)), 'Duplicate selected paper pages'
        check_page(item['pdf_page'])
        check_pages(item['required_source_pdf_pages'])
        assert item['pdf_page'] in item['required_source_pdf_pages'], 'Item page missing from required source pages'
        assert type(item['official_points']) in (int,float) and 0<item['official_points']<=100, 'Invalid selected item marks'
        assert item['requires_source_access'] is True, 'Selected item requires source access'
        assert isinstance(item['map_sections'],list) and item['map_sections'] and all(isinstance(section,str) and section.strip() for section in item['map_sections']), 'Missing selected item scope mapping'
        if 'marks_provenance' in item:
            assert isinstance(item['marks_provenance'],str) and item['marks_provenance'].strip(), 'Invalid marks provenance'
        if 'required_source_parts' in item:
            assert isinstance(item['required_source_parts'],list) and item['required_source_parts'], 'Missing selected dependency locators'
            for part in item['required_source_parts']:
                assert isinstance(part,dict) and set(part)=={'pdf_pages','locator'}, 'Selected dependency contains locators only'
                check_pages(part['pdf_pages'])
                assert isinstance(part['locator'],str) and part['locator'].strip(), 'Missing selected dependency locator'
                assert set(part['pdf_pages'])<=set(item['required_source_pdf_pages']), 'Dependency page missing from required source pages'
        if 'reviewed_parts' in source:
            assert isinstance(source['reviewed_parts'],list), 'Invalid paper review locators'
            for part in source['reviewed_parts']:
                assert isinstance(part,dict) and set(part)=={'pdf_page','locator'}, 'Selected paper review contains locators only'
                check_page(part['pdf_page'])
                assert isinstance(part['locator'],str) and part['locator'].strip(), 'Invalid paper review locator'

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--field',choices=['1','2','3','4'],default='2')
    parser.add_argument('--root',type=Path,help='Validate a fully staged plugin')
    args=parser.parse_args()
    if args.field!='2':
        assert args.root is not None, 'New fields must be staged before validation'
    field=profile(args.field)
    if args.root is None:
        # Source authoring contains all subjects; the CLI owns this temporary runtime.
        import tempfile
        from stage import stage
        with tempfile.TemporaryDirectory(prefix='lyceum-validate-') as temporary:
            root=Path(temporary)
            stage(field,root)
            validate(root,field)
    else:
        validate(args.root,field)
