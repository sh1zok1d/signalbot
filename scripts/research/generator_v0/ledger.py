"""SQLite is the authority; JSON reports are replaceable views, never partial truth."""
from __future__ import annotations
import contextlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .context import ContractError, canonical, digest

class Ledger:
    def __init__(self,path,config=None):
        self.db=sqlite3.connect(path,timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS calls(key TEXT PRIMARY KEY,request TEXT NOT NULL,state TEXT NOT NULL,reserved INTEGER NOT NULL,response TEXT,cost INTEGER,usage TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS cards(id TEXT PRIMARY KEY,card TEXT NOT NULL,decision TEXT);
        CREATE TABLE IF NOT EXISTS events(n INTEGER PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS results(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
        ''')
        if config is not None:
            old=self.get('config')
            if old is not None and old!=config:raise ContractError('resume configuration differs')
            if old is None:
                with self.db:self.set('config',config);self.set('status','CREATED')

    @classmethod
    def open_readonly(cls,path):
        self=object.__new__(cls)
        uri='file:{}?mode=ro'.format(Path(path).resolve().as_posix())
        self.db=sqlite3.connect(uri,uri=True,timeout=30)
        return self

    def close(self):self.db.close()

    def spent_micro_usd(self):
        return self.db.execute('SELECT COALESCE(SUM(COALESCE(cost,reserved)),0) FROM calls').fetchone()[0]

    def import_complete(self,key,request,reserved,response,cost,usage,provenance):
        if type(reserved)!=int or reserved<0 or type(cost)!=int or not 0<=cost<=reserved:
            raise ContractError('invalid imported cost')
        if digest(request)!=key:raise ContractError('imported key does not match request identity')
        if not isinstance(response,dict) or not response.get('raw') or not response.get('response_id') or not response.get('raw_sha256') or 'provider_envelope' not in response:
            raise ContractError('imported complete response missing identity')
        if not isinstance(usage,dict):raise ContractError('imported usage required')
        required=('SOURCE_RUN_ID','SOURCE_CALL_KEY','SOURCE_RESPONSE_ID','SOURCE_RAW_RESPONSE_SHA256')
        if not isinstance(provenance,dict) or any(not provenance.get(k) for k in required):
            raise ContractError('imported provenance required')
        if provenance['SOURCE_CALL_KEY']!=key:raise ContractError('imported source call key mismatch')
        if provenance['SOURCE_RESPONSE_ID']!=response['response_id']:raise ContractError('imported response_id mismatch')
        if provenance['SOURCE_RAW_RESPONSE_SHA256']!=response['raw_sha256']:raise ContractError('imported raw hash mismatch')
        blob={**response,**{k:provenance[k] for k in required}}
        cap=self.get('config')['CAP_MICRO_USD']
        with self.transaction():
            if self.db.execute('SELECT 1 FROM calls WHERE key=?',(key,)).fetchone():
                raise ContractError('imported call already present')
            spent=self.db.execute('SELECT COALESCE(SUM(COALESCE(cost,reserved)),0) FROM calls').fetchone()[0]
            if spent+cost>cap:raise ContractError('imported cost exceeds campaign cap')
            self.db.execute('INSERT INTO calls(key,request,state,reserved,response,cost,usage,error) VALUES (?,?,?,?,?,?,?,?)',
                            (key,canonical(request),'COMPLETE',reserved,canonical(blob),cost,canonical(usage),None))
            self.event('CALL_IMPORTED',dict(provenance))
    def set(self,key,value):self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(key,canonical(value)))
    def get(self,key):
        row=self.db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback();raise

    def reserve(self,key,request,bound,cap):
        if type(bound)!=int or bound<0 or type(cap)!=int or not 0<=cap<=30_000_000:
            raise ContractError('invalid budget')
        with self.transaction():
            row=self.db.execute('SELECT request,state,response FROM calls WHERE key=?',(key,)).fetchone()
            if row:
                if row[0]!=canonical(request):raise ContractError('request identity collision')
                if row[1]=='COMPLETE':return json.loads(row[2])
                if row[1]=='BACKGROUND_SUBMITTED':
                    payload=json.loads(row[2]) if row[2] else {}
                    payload['_resume_background']=True
                    return payload
                raise ContractError('uncertain prior attempt; manual reconciliation required, never automatic replay')
            spent=self.db.execute('SELECT COALESCE(SUM(COALESCE(cost,reserved)),0) FROM calls').fetchone()[0]
            if spent+bound>cap:raise ContractError('budget exceeded before provider call')
            self.db.execute('INSERT INTO calls(key,request,state,reserved) VALUES (?,?,?,?)',(key,canonical(request),'RESERVED',bound))
        return None

    def submit_background(self,key,tracker):
        with self.transaction():
            row=self.db.execute('SELECT state FROM calls WHERE key=?',(key,)).fetchone()
            if row is None or row[0] not in ('RESERVED','BACKGROUND_SUBMITTED'):raise ContractError('invalid background submit')
            if not isinstance(tracker,dict) or not tracker.get('response_id'):raise ContractError('background response_id required')
            self.db.execute('UPDATE calls SET state=?,response=?,error=NULL WHERE key=?',('BACKGROUND_SUBMITTED',canonical(tracker),key))

    def finish(self,key,response,cost,usage):
        with self.transaction():
            row=self.db.execute('SELECT reserved,state FROM calls WHERE key=?',(key,)).fetchone()
            if row is None or row[1] not in ('RESERVED','BACKGROUND_SUBMITTED'):raise ContractError('invalid provider completion')
            if type(cost)!=int or not 0<=cost<=row[0]:raise ContractError('provider cost exceeds reserved bound')
            self.db.execute('UPDATE calls SET state=?,response=?,cost=?,usage=?,error=NULL WHERE key=?',('COMPLETE',canonical(response),cost,canonical(usage),key))

    def attach_parsed(self,key,raw):
        with self.transaction():
            row=self.db.execute('SELECT state,response FROM calls WHERE key=?',(key,)).fetchone()
            if row is None or row[0]!='COMPLETE' or not row[1]:raise ContractError('invalid parsed attach')
            blob=json.loads(row[1]);blob['raw']=raw
            self.db.execute('UPDATE calls SET response=? WHERE key=?',(canonical(blob),key))

    def failed(self,key,error,wire_sha256=None,state='UNCERTAIN',envelope=None,cost=None,usage=None):
        if state not in ('UNCERTAIN','FAILED'):raise ContractError('invalid failure state')
        blob=envelope if envelope is not None else ({'raw_sha256':wire_sha256} if wire_sha256 else None)
        invalid=False
        persist_cost=persist_usage=None
        with self.transaction():
            row=self.db.execute('SELECT reserved FROM calls WHERE key=?',(key,)).fetchone()
            if row is None:raise ContractError('invalid failure')
            if cost is not None or usage is not None:
                if type(cost)!=int or not 0<=cost<=row[0] or usage is None:invalid=True
                else:persist_cost,persist_usage=cost,canonical(usage)
            self.db.execute('UPDATE calls SET state=?,error=?,response=?,cost=?,usage=? WHERE key=?',(state,str(error)[:500],canonical(blob) if blob is not None else None,persist_cost,persist_usage,key))
        if invalid:raise ContractError('provider cost exceeds reserved bound')

    def export_calls(self):
        result=[]
        for key,request,state,reserved,response,cost,usage,error in self.db.execute('SELECT * FROM calls ORDER BY rowid'):
            req=json.loads(request);resp=json.loads(response) if response else None
            result.append({'CALL_KEY':key,'RUN_ID':self.get('config')['RUN_ID'],'PROMPT_VERSION':req['prompt_version'],'CONTEXT_DIGEST':digest(req['context']),'MODEL_PROVIDER':req['provider'],'MODEL_ID':req['model'],'MODEL_PARAMETERS':req['parameters'],'MODEL_REQUEST_PARAMS':req.get('model_request_params'),'RAW_RESPONSE_SHA256':(resp or {}).get('raw_sha256') if resp else None,'RESPONSE_ID':(resp or {}).get('response_id') if resp else None,'PROVIDER_STATUS':(resp or {}).get('provider_status') if resp else None,'STATE':state,'RESERVED_MICRO_USD':reserved,'COST_MICRO_USD':cost,'USAGE':json.loads(usage) if usage else None,'ERROR':error,'SOURCE_RUN_ID':(resp or {}).get('SOURCE_RUN_ID') if resp else None,'SOURCE_CALL_KEY':(resp or {}).get('SOURCE_CALL_KEY') if resp else None,'SOURCE_RESPONSE_ID':(resp or {}).get('SOURCE_RESPONSE_ID') if resp else None,'SOURCE_RAW_RESPONSE_SHA256':(resp or {}).get('SOURCE_RAW_RESPONSE_SHA256') if resp else None})
        return result

    def save_card(self,card,decision=None):
        self.db.execute('INSERT INTO cards VALUES (?,?,?)',(card['CANDIDATE_ID'],canonical(card),canonical(decision)))

    def event(self,kind,payload):
        self.db.execute('INSERT INTO events(kind,payload) VALUES (?,?)',(kind,canonical(payload)))

    def mutate(self,card_id,field,after,reason,actor,validate):
        if not isinstance(reason,str) or not reason.strip() or not isinstance(actor,str) or not actor.strip() or field=='CANDIDATE_ID':raise ContractError('mutation audit required')
        with self.transaction():
            row=self.db.execute('SELECT card FROM cards WHERE id=?',(card_id,)).fetchone()
            if row is None:raise ContractError('unknown candidate')
            card=json.loads(row[0])
            if field not in card:raise ContractError('unknown mutation field')
            before=card[field];card[field]=after;validate(card)
            self.event('HUMAN_MUTATION',{'CANDIDATE_ID':card_id,'field':field,'before':before,'after':after,'reason':reason,'actor':actor,'time':datetime.now(timezone.utc).isoformat()})
            self.db.execute('UPDATE cards SET card=?,decision=NULL WHERE id=?',(canonical(card),card_id))
            self.db.execute('DELETE FROM results')
            self.set('status','MUTATED_REQUIRES_REVIEW')

def data_gaps(survivors):
    """Input is mutually distinct Stream B survivors, after batch novelty adjudication."""
    groups={}
    for card in survivors:
        key=card['DATA_GAP_CLASS']
        groups.setdefault(key,[]).append(card)
    return [{
        'MISSING_DATA_CLASS':key,
        'MISSING_OBSERVABLE':sorted({x for c in cards for x in c['MISSING_OBSERVABLES']}),
        'MECHANISM_REGION':sorted({c['MECHANISM'] for c in cards}),
        'EXPECTED_INFORMATION_GAIN':{c['CANDIDATE_ID']:c['EXPECTED_INFORMATION_GAIN'] for c in cards},
        'NUMBER_OF_DISTINCT_CANDIDATES_BLOCKED':len(cards),
        'IS_THIS_A_DUPLICATE_DATA_DEMAND':len(cards)>1,
        'ESTIMATED_ACQUISITION_COST':'UNASSESSED_REQUIRES_HUMAN_FEASIBILITY',
        'PROVENANCE_RISK':sorted({c['DATA_STATUS'] for c in cards}),
        'WOULD_DATA_UNLOCK_DISTINCT_MECHANISM_SPACE':True,
    } for key,cards in sorted(groups.items())]
