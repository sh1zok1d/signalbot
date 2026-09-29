"""B2: a journal recognized as SEALED rejects every mutating operation, whatever
its path, file name or directory, through the library as well as the CLI.
Fixtures are synthetic sealed journals and tmp copies; v6/v7 are never opened for writing."""
import hashlib
import json
import shutil
import sqlite3
import pytest
from pathlib import Path
from scripts.research.generator_v0 import ledger as ledger_mod
from scripts.research.generator_v0.ledger import Ledger,SealedJournal,sealed_reason

REPO=Path(__file__).resolve().parents[2]
V7=REPO/'docs/research/generator_v0_first_shadow_v7/run.sqlite'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def synthetic(path):
    l=Ledger(path,{'RUN_ID':'syn','CAP_MICRO_USD':1000})
    l.reserve('k',{'role':'RED_TEAM','slot':'s'},10,1000);l.mark_dispatched('k');l.finish('k',{'raw':'{}'},5,{})
    return l

MUTATIONS=[
    ('set',lambda l:l.set('status','CREATED')),
    ('event',lambda l:l.event('X',{})),
    ('reserve',lambda l:l.reserve('new',{'x':1},1,1000)),
    ('mark_dispatched',lambda l:l.mark_dispatched('k')),
    ('finish',lambda l:l.finish('k',{'raw':'x'},1,{})),
    ('failed',lambda l:l.failed('k','x',state='UNCERTAIN')),
    ('reconcile',lambda l:l.reconcile('k','UNKNOWN',None,'op','r')),
    ('record_candidate',lambda l:l.record_candidate('C001','generation:0','k','GENERATOR_CONTRACT_V02','HARD_FAIL',None,[])),
    ('set_candidate_review',lambda l:l.set_candidate_review('C001','REVIEWED',[])),
    ('save_card',lambda l:l.save_card({'CANDIDATE_ID':'C001'})),
    ('transaction',lambda l:l.transaction().__enter__()),
    ('import_complete',lambda l:l.import_complete('z',{},1,{},1,{},{})),
    ('mutate',lambda l:l.mutate('C001','NAME','x','r','a',lambda c:None)),
]

@pytest.mark.parametrize('where',['same','renamed','other_dir'])
def test_meta_sealed_journal_refuses_writable_open_at_any_path(tmp_path,where):
    src=tmp_path/'run.sqlite';l=synthetic(src);l.seal('op','synthetic sealed fixture')
    target={'same':src,'renamed':tmp_path/'copy_named_anything.db','other_dir':tmp_path/'x'/'y'/'run.sqlite'}[where]
    if target!=src:target.parent.mkdir(parents=True,exist_ok=True);shutil.copy(src,target)
    before=sha(target)
    with pytest.raises(SealedJournal):Ledger(target)
    with pytest.raises(SealedJournal):Ledger(target,{'RUN_ID':'syn','CAP_MICRO_USD':1000})
    assert sha(target)==before and sorted(p.name for p in target.parent.iterdir() if p.name.startswith(target.name))==[target.name]

@pytest.mark.parametrize('name,mutation',MUTATIONS,ids=[m[0] for m in MUTATIONS])
def test_every_mutation_refused_through_a_read_handle(tmp_path,name,mutation):
    src=tmp_path/'run.sqlite';l=synthetic(src);l.seal('op','sealed')
    before=sha(src)
    r=Ledger.open_readonly(src)
    with pytest.raises(SealedJournal):mutation(r)
    r.close()
    assert sha(src)==before

def test_reads_are_side_effect_free(tmp_path):
    src=tmp_path/'run.sqlite';l=synthetic(src);l.seal('op','sealed')
    before=sha(src)
    assert sealed_reason(src)=='journal meta is SEALED'
    r=Ledger.open_readonly(src)
    assert r.spent_micro_usd()==5 and r.total_charged_micro_usd()==5 and r.get('config')['RUN_ID']=='syn'
    assert [x['STATE'] for x in r.export_calls()]==['COMPLETE'] and r.candidates()==[] and r.unresolved_calls()==[]
    r.close()
    assert sha(src)==before and sorted(p.name for p in tmp_path.iterdir())==['run.sqlite']

def test_registry_hash_seals_a_journal_without_meta_marker(tmp_path,monkeypatch):
    """A synthetic journal listed only by content hash in a (temporary) registry."""
    src=tmp_path/'plain.sqlite';l=synthetic(src);l.db.execute('PRAGMA wal_checkpoint(TRUNCATE)');l.db.execute('PRAGMA journal_mode=DELETE');l.close()
    reg=tmp_path/'registry.json'
    reg.write_text(json.dumps({'RUNS':[{'JOURNAL_SHA256':sha(src),'RUN_ID':'synthetic'}]}),encoding='utf-8')
    monkeypatch.setattr(ledger_mod,'SEALED_REGISTRY',reg)
    for target in (src,tmp_path/'a'/'b.sqlite'):
        target.parent.mkdir(parents=True,exist_ok=True)
        if target!=src:shutil.copy(src,target)
        before=sha(target)
        with pytest.raises(SealedJournal,match='sealed registry'):Ledger(target)
        assert sha(target)==before

def test_tmp_copy_of_v7_is_refused_by_the_library(tmp_path):
    """A copy under an unrelated name (the tracked v7 file itself is never opened for writing)."""
    target=tmp_path/'nested'/'not_v7.sqlite';target.parent.mkdir();shutil.copy(V7,target)
    before=sha(target)
    with pytest.raises(SealedJournal,match='sealed registry'):Ledger(target)
    r=Ledger.open_readonly(target)
    with pytest.raises(SealedJournal):r.reserve('x',{},1,1)
    r.close()
    assert sha(target)==before

def test_unsealed_journal_still_writable(tmp_path):
    l=synthetic(tmp_path/'run.sqlite');l.close()
    l=Ledger(tmp_path/'run.sqlite');l.event('OK',{});l.db.commit();l.close()
