"""Negative cases for the release/source-reader invariants; no source mutation."""
import importlib.util, json
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('validator',R/'scripts/validate.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
original=Path.read_text
card=R/'skills/lyceum-study/references/study-card.md'
manifest=R/'plugin.json'
def reject(target,transform,expected):
 def mutated(self,*args,**kwargs):
  text=original(self,*args,**kwargs)
  return transform(text) if self==target else text
 with patch.object(Path,'read_text',mutated):
  try:v.validate()
  except AssertionError as error:
   assert expected in str(error),error
   print('PASS: rejects '+expected)
  else:raise AssertionError('Bad fixture unexpectedly passed')
reject(card,lambda t:t+'\n[unreadable root manifest](../../../plugin.json)\n','Skill reader cannot expose plugin-root link')
def next_version(text):
 data=json.loads(text);major,minor,patch=map(int,data['version'].split('.'))
 data['version']=f'{major}.{minor}.{patch+1}'
 return json.dumps(data)
reject(manifest,next_version,'Runtime release version mismatch')

book_catalog=R/'skills/lyceum-study/references/shared/textbooks/catalog.json'
def bundled_book(text):
 data=json.loads(text);data['books'][0]['file']='../official/syllabus-2027.pdf'
 return json.dumps(data)
reject(book_catalog,bundled_book,'Link-only source cannot include local file')
source_registry=R/'skills/lyceum-study/references/shared/sources.json'
def misleading_snapshot(text):
 data=json.loads(text)
 source=next(s for s in data['sources'] if s.get('distribution')=='link-only')
 source['snapshot_included']=True
 return json.dumps(data)
reject(source_registry,misleading_snapshot,'Link-only source cannot claim bundled snapshot')

reviewed_greek=R/'skills/lyceum-exams/references/reviewed-greek.json'
def wrong_container_page(text):
 data=json.loads(text);data['items'][0]['source_pdf_page']=data['items'][0]['pdf_page']
 return json.dumps(data)
reject(reviewed_greek,wrong_container_page,'Wrong source-container page')

chemistry=json.loads((R/'skills/lyceum-exams/references/reviewed-chemistry.json').read_text())
item=next(i for i in chemistry['items'] if i['id']=='chemistry-2025-B3')
assert 'source_typo_note' not in item, 'Nonexistent Chemistry2025B3 typo reintroduced'
assert item['url']=='https://www.minedu.gov.gr/publications/docs2025/panelladikes_2025_iounios/them_ximeia_gel_250604.pdf'
assert item['sha256']=='ed5280d8c2c3628daee2fe6665da3b09ed4c7828d8c9efb935a7215bb40b3ef1'
assert item['source_pdf_page']==3 and item['official_points']==5
print('PASS: Chemistry2025B3 uses the verified primary source without a false typo claim')

reviewed_chemistry=R/'skills/lyceum-exams/references/reviewed-chemistry.json'
def stored_answer(text):
 data=json.loads(text);data['items'][0]['answer']='δ'
 return json.dumps(data)
reject(reviewed_chemistry,stored_answer,'Exam records contain locators only')
reviewed_physics=R/'skills/lyceum-exams/references/reviewed-physics.json'
def stored_formula(text):
 data=json.loads(text)
 item=next(i for i in data['items'] if i.get('required_formula_access'))
 item['required_formula_access']['formulas']=['E=hf']
 return json.dumps(data)
reject(reviewed_physics,stored_formula,'Exam dependency contains unexpected answer/data field')
