"""SQLite is the authority; JSON reports are replaceable views, never partial truth.

Call states and how each is charged against the campaign ceiling:
  RESERVED                                   -> reserved bound; never sent (dispatch protocol)
  DISPATCHED, BACKGROUND_SUBMITTED, UNCERTAIN -> reserved bound (a POST may have happened)
  COMPLETE, FAILED_WITH_COST, RECONCILED_BILLED -> recorded actual cost
  RECONCILED_UNKNOWN                         -> reserved bound; logical call closed forever
  FAILED_NOT_BILLED, RECONCILED_NOT_BILLED   -> 0 (model work never ran)
  FAILED (pre-repair journals only)          -> COALESCE(cost, reserved)
The ceiling check is lineage prior spend + journal charges + new bound <= cap.

Dispatch protocol (meta DISPATCH_PROTOCOL=2, every journal created by this code):
a call is committed DISPATCHED before any byte is sent. A RESERVED row therefore
never left the machine and is re-dispatched under the same key on resume. A row
that may have been POSTed (DISPATCHED, UNCERTAIN, or RESERVED in a journal
without the protocol) is never re-sent automatically; the operator must
reconcile it, and NOT_BILLED requires provider-side evidence tied to a
recorded response_id. Without evidence the only exit is UNKNOWN, which charges
the reserved bound and closes the logical call so it is never POSTed again.

Sealing: a journal whose file SHA256 is in the sealed registry, or whose meta
holds SEALED, refuses every mutating operation (writable open, and every write
through a read-only handle), whatever its path or file name.
"""
from __future__ import annotations
import contextlib
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .context import ContractError, canonical, digest

OPEN_STATES=('RESERVED','DISPATCHED','UNCERTAIN')
POSSIBLY_POSTED=('DISPATCHED','UNCERTAIN')
BILLED_CLOSED=('FAILED_WITH_COST','RECONCILED_BILLED','RECONCILED_UNKNOWN','FAILED')
DISPATCH_PROTOCOL=2
SEALED_REGISTRY=Path(__file__).resolve().parents[3]/'docs/research/GENERATOR_V0_SEALED_RUNS.json'
NOT_BILLED_PROVIDER_STATUSES=('failed','cancelled')
NOT_BILLED_CLOSED=('FAILED_NOT_BILLED','RECONCILED_NOT_BILLED')
CHARGE_SQL=("SELECT COALESCE(SUM(CASE "
            "WHEN state IN ('COMPLETE','FAILED_WITH_COST','RECONCILED_BILLED') THEN cost "
            "WHEN state IN ('FAILED_NOT_BILLED','RECONCILED_NOT_BILLED') THEN 0 "
            "ELSE COALESCE(cost,reserved) END),0) FROM calls")
CANDIDATE_STATES=('VALID','HARD_FAIL','REVIEWED','REVIEW_FAILED')

class InfrastructureStop(ContractError):
    """Campaign-level condition: safe continuation needs an operator or more budget."""
class BudgetExceeded(InfrastructureStop):pass
class CallUncertain(InfrastructureStop):pass
class SealedJournal(ContractError):
    """A sealed journal was about to be mutated."""
class LogicalCallClosed(ContractError):
    """The logical call was closed by an evidence-free reconciliation; never POST it again."""
class AttemptClosed(ContractError):
    def __init__(self,state):super().__init__('attempt closed: '+state);self.state=state

def archive_connect(path):
    """Read a sealed/archival journal without creating WAL side files."""
    path=Path(path).resolve()
    wal=Path(str(path)+'-wal')
    if wal.exists() and wal.stat().st_size>0:raise ContractError('archive has an uncheckpointed WAL; refuse to read partial state')
    return sqlite3.connect('file:{}?mode=ro&immutable=1'.format(path.as_posix()),uri=True,timeout=30)

def _file_sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()

def sealed_hashes():
    return {r['JOURNAL_SHA256'] for r in json.loads(SEALED_REGISTRY.read_text(encoding='utf-8'))['RUNS']}

def sealed_reason(path):
    """Why path is a sealed journal, or None. Side-effect free (immutable read)."""
    path=Path(path)
    if not path.exists():return None
    if _file_sha256(path) in sealed_hashes():return 'journal content hash is in the sealed registry'
    wal=Path(str(path)+'-wal')
    if wal.exists() and wal.stat().st_size>0:return None   # live journal; meta is re-checked after open
    try:
        db=sqlite3.connect('file:{}?mode=ro&immutable=1'.format(path.resolve().as_posix()),uri=True)
        try:row=db.execute("SELECT value FROM meta WHERE key='SEALED'").fetchone()
        finally:db.close()
    except sqlite3.DatabaseError:
        return None
    return 'journal meta is SEALED' if row else None

class Ledger:
    readonly=False
    def __init__(self,path,config=None):
        reason=sealed_reason(path)
        if reason:raise SealedJournal('sealed journal refuses writable open: '+reason)
        new=not Path(path).exists()
        self.db=sqlite3.connect(path,timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS calls(key TEXT PRIMARY KEY,request TEXT NOT NULL,state TEXT NOT NULL,reserved INTEGER NOT NULL,response TEXT,cost INTEGER,usage TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS cards(id TEXT PRIMARY KEY,card TEXT NOT NULL,decision TEXT);
        CREATE TABLE IF NOT EXISTS events(n INTEGER PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS results(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,round TEXT NOT NULL,call_key TEXT,contract TEXT NOT NULL,state TEXT NOT NULL,card TEXT,reasons TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS closed_calls(slot TEXT PRIMARY KEY,call_key TEXT NOT NULL,reason TEXT NOT NULL);
        ''')
        if self.get('SEALED') is not None:
            self.db.close();raise SealedJournal('sealed journal refuses writable open: journal meta is SEALED')
        if new:
            with self.db:self.set('DISPATCH_PROTOCOL',DISPATCH_PROTOCOL)
        if config is not None:
            old=self.get('config')
            if old is not None and old!=config:raise ContractError('resume configuration differs')
            if old is None:
                with self.db:self.set('config',config);self.set('status','CREATED')

    @classmethod
    def open_readonly(cls,path):
        """Immutable read handle. Every mutating method refuses."""
        self=object.__new__(cls)
        self.db=archive_connect(path)
        self.readonly=True
        return self

    def _writable(self):
        if self.readonly:raise SealedJournal('read-only journal handle refuses mutation')

    def dispatch_protocol(self):
        return self.get('DISPATCH_PROTOCOL')==DISPATCH_PROTOCOL

    def seal(self,actor,reason):
        """Mark this journal sealed (meta SEALED), checkpoint it and close the handle."""
        if not isinstance(actor,str) or not actor.strip() or not isinstance(reason,str) or not reason.strip():raise ContractError('actor and reason required')
        with self.transaction():
            open_rows=self.db.execute("SELECT count(*) FROM calls WHERE state IN ('RESERVED','DISPATCHED','UNCERTAIN','BACKGROUND_SUBMITTED')").fetchone()[0]
            self.set('SEALED',{'ACTOR':actor.strip(),'REASON':reason.strip(),'OPEN_CALLS':open_rows,'TIME':datetime.now(timezone.utc).isoformat()})
            self.event('JOURNAL_SEALED',{'ACTOR':actor.strip(),'REASON':reason.strip()})
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.close();self.readonly=True

    def close(self):self.db.close()

    def spent_micro_usd(self):
        """Charges recorded in this journal only."""
        return self.db.execute(CHARGE_SQL).fetchone()[0]

    def lineage_prior_micro_usd(self):
        lineage=self.get('lineage') or {}
        value=lineage.get('PRIOR_SPEND_MICRO_USD',0)
        if type(value) is not int or value<0:raise ContractError('invalid lineage prior spend')
        return value

    def total_charged_micro_usd(self):
        """Owner-ceiling spend: carried lineage spend plus this journal."""
        return self.lineage_prior_micro_usd()+self.spent_micro_usd()

    def import_complete(self,key,request,reserved,response,cost,usage,provenance):
        self._writable()
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
            if self.total_charged_micro_usd()+cost>cap:raise ContractError('imported cost exceeds campaign cap')
            self.db.execute('INSERT INTO calls(key,request,state,reserved,response,cost,usage,error) VALUES (?,?,?,?,?,?,?,?)',
                            (key,canonical(request),'COMPLETE',reserved,canonical(blob),cost,canonical(usage),None))
            self.event('CALL_IMPORTED',dict(provenance))
    def set(self,key,value):
        self._writable()
        self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(key,canonical(value)))
    def get(self,key):
        row=self.db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None

    @contextlib.contextmanager
    def transaction(self):
        self._writable()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback();raise

    def reserve(self,key,request,bound,cap):
        """COMPLETE -> saved response (never re-POST). Closed attempt -> AttemptClosed.
        RESERVED under the dispatch protocol -> None (never sent; dispatch it now).
        DISPATCHED/UNCERTAIN (or RESERVED without the protocol) -> CallUncertain.
        New -> reserve bound or BudgetExceeded."""
        self._writable()
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
                if row[1] in BILLED_CLOSED or row[1] in NOT_BILLED_CLOSED:raise AttemptClosed(row[1])
                if row[1]=='RESERVED' and self.dispatch_protocol():return None
                raise CallUncertain('uncertain prior attempt; manual reconciliation required, never automatic replay')
            if self.total_charged_micro_usd()+bound>cap:raise BudgetExceeded('budget exceeded before provider call')
            self.db.execute('INSERT INTO calls(key,request,state,reserved) VALUES (?,?,?,?)',(key,canonical(request),'RESERVED',bound))
        return None

    def mark_dispatched(self,key):
        """Commit DISPATCHED before any byte of the request is sent."""
        self._writable()
        with self.transaction():
            row=self.db.execute('SELECT state FROM calls WHERE key=?',(key,)).fetchone()
            if row is None or row[0]!='RESERVED':raise ContractError('dispatch requires a RESERVED call')
            self.db.execute("UPDATE calls SET state='DISPATCHED' WHERE key=?",(key,))

    def logical_call_closed(self,slot):
        row=self.db.execute('SELECT call_key,reason FROM closed_calls WHERE slot=?',(slot,)).fetchone()
        return {'CALL_KEY':row[0],'REASON':row[1]} if row else None

    def unresolved_calls(self):
        return [{'CALL_KEY':k,'STATE':st,'RESERVED_MICRO_USD':r} for k,st,r in self.db.execute("SELECT key,state,reserved FROM calls WHERE state IN ('RESERVED','DISPATCHED','UNCERTAIN','BACKGROUND_SUBMITTED') ORDER BY rowid")]

    def call_state(self,key):
        row=self.db.execute('SELECT state FROM calls WHERE key=?',(key,)).fetchone()
        return row[0] if row else None

    def complete_raw(self,key):
        row=self.db.execute('SELECT state,response FROM calls WHERE key=?',(key,)).fetchone()
        if row is None or row[0]!='COMPLETE' or not row[1]:raise ContractError('imported call is not COMPLETE')
        return json.loads(row[1])['raw']

    def submit_background(self,key,tracker):
        self._writable()
        with self.transaction():
            row=self.db.execute('SELECT state FROM calls WHERE key=?',(key,)).fetchone()
            if row is None or row[0] not in ('RESERVED','DISPATCHED','BACKGROUND_SUBMITTED'):raise ContractError('invalid background submit')
            if not isinstance(tracker,dict) or not tracker.get('response_id'):raise ContractError('background response_id required')
            self.db.execute('UPDATE calls SET state=?,response=?,error=NULL WHERE key=?',('BACKGROUND_SUBMITTED',canonical(tracker),key))

    def finish(self,key,response,cost,usage):
        self._writable()
        with self.transaction():
            row=self.db.execute('SELECT reserved,state FROM calls WHERE key=?',(key,)).fetchone()
            if row is None or row[1] not in ('RESERVED','DISPATCHED','BACKGROUND_SUBMITTED'):raise ContractError('invalid provider completion')
            if type(cost)!=int or not 0<=cost<=row[0]:raise ContractError('provider cost exceeds reserved bound')
            self.db.execute('UPDATE calls SET state=?,response=?,cost=?,usage=?,error=NULL WHERE key=?',('COMPLETE',canonical(response),cost,canonical(usage),key))

    def failed(self,key,error,wire_sha256=None,state='UNCERTAIN',envelope=None,cost=None,usage=None):
        """Close an attempt. FAILED_NOT_BILLED charges 0; FAILED_WITH_COST charges the
        billed usage cost, or the reserved bound when usage is unknown (COST_BASIS)."""
        self._writable()
        if state=='FAILED':state='FAILED_WITH_COST'
        if state not in ('UNCERTAIN','FAILED_NOT_BILLED','FAILED_WITH_COST'):raise ContractError('invalid failure state')
        blob=dict(envelope) if envelope is not None else {}
        if wire_sha256:blob.setdefault('raw_sha256',wire_sha256)
        invalid=False
        with self.transaction():
            row=self.db.execute('SELECT reserved,state FROM calls WHERE key=?',(key,)).fetchone()
            if row is None:raise ContractError('invalid failure')
            reserved=row[0];persist_cost=persist_usage=None
            if state=='FAILED_NOT_BILLED':
                persist_cost=0;blob['COST_BASIS']='NOT_BILLED'
            elif state=='FAILED_WITH_COST':
                if cost is not None and usage is not None and type(cost)==int and 0<=cost<=reserved:
                    persist_cost,persist_usage=cost,canonical(usage);blob['COST_BASIS']='USAGE'
                else:
                    invalid=cost is not None and not (type(cost)==int and 0<=cost<=reserved)
                    persist_cost=reserved;blob['COST_BASIS']='RESERVED_BOUND'
            else:
                if cost is not None or usage is not None:
                    if type(cost)!=int or not 0<=cost<=reserved or usage is None:invalid=True
                    else:persist_cost,persist_usage=cost,canonical(usage)
            self.db.execute('UPDATE calls SET state=?,error=?,response=?,cost=?,usage=? WHERE key=?',(state,str(error)[:500],canonical(blob) if blob else None,persist_cost,persist_usage,key))
        if invalid:raise ContractError('provider cost exceeds reserved bound')

    def reconcile(self,key,resolution,cost_micro_usd,actor,reason,evidence=''):
        """Operator resolution of an attempt that may have been POSTed. Offline; never POSTs.

        BILLED      cost within the reserved bound and non-empty evidence; the
                    attempt is closed with that cost (a later content attempt is a
                    new, separately reserved and audited call).
        NOT_BILLED  only with provider-side evidence: a JSON object whose
                    PROVIDER_RESPONSE_ID equals the response_id recorded on this
                    row and whose PROVIDER_STATUS is failed or cancelled with
                    BILLED_OUTPUT_TOKENS 0. Operator assertion alone is refused.
        UNKNOWN     no evidence; charges the reserved bound and closes the
                    logical call (role and slot) so it is never POSTed again.
        """
        self._writable()
        if not isinstance(actor,str) or not actor.strip() or not isinstance(reason,str) or not reason.strip():
            raise ContractError('actor and reason required')
        if resolution not in ('NOT_BILLED','BILLED','UNKNOWN'):raise ContractError('resolution must be NOT_BILLED, BILLED or UNKNOWN')
        ev=evidence
        if isinstance(ev,str) and ev.strip().startswith('{'):
            try:ev=json.loads(ev)
            except ValueError:raise ContractError('evidence is not valid JSON')
        with self.transaction():
            row=self.db.execute('SELECT reserved,state,response,request FROM calls WHERE key=?',(key,)).fetchone()
            if row is None:raise ContractError('unknown call key')
            reserved,state,response,request=row
            if state not in OPEN_STATES:raise ContractError('only RESERVED, DISPATCHED or UNCERTAIN calls can be reconciled')
            if state=='RESERVED' and self.dispatch_protocol():
                raise ContractError('RESERVED call was never dispatched; resume re-dispatches it under the same key')
            recorded=(json.loads(response) if response else {}).get('response_id')
            slot=json.loads(request).get('slot')
            role=json.loads(request).get('role')
            if resolution=='NOT_BILLED':
                if not isinstance(ev,dict):raise ContractError('NOT_BILLED requires provider-side evidence for a call that may have been POSTed')
                if not recorded or ev.get('PROVIDER_RESPONSE_ID')!=recorded:
                    raise ContractError('NOT_BILLED evidence must name the provider response_id recorded for this call')
                if ev.get('PROVIDER_STATUS') not in NOT_BILLED_PROVIDER_STATUSES or ev.get('BILLED_OUTPUT_TOKENS')!=0:
                    raise ContractError('NOT_BILLED evidence must show a failed or cancelled response with zero billed output tokens')
                cost=0;new='RECONCILED_NOT_BILLED'
            elif resolution=='BILLED':
                if type(cost_micro_usd) is not int or not 0<cost_micro_usd<=reserved:raise ContractError('billed cost must be a positive integer within the reserved bound')
                if not ev:raise ContractError('BILLED requires evidence (provider usage record or response id)')
                cost=cost_micro_usd;new='RECONCILED_BILLED'
            else:
                cost=reserved;new='RECONCILED_UNKNOWN'
                self.db.execute('INSERT OR REPLACE INTO closed_calls VALUES (?,?,?)',(str(role)+'|'+str(slot),key,'reconciled UNKNOWN: '+reason.strip()))
            payload={'CALL_KEY':key,'PRIOR_STATE':state,'RESOLUTION':resolution,'COST_MICRO_USD':cost,'RESERVED_MICRO_USD':reserved,
                     'ACTOR':actor.strip(),'REASON':reason.strip(),'EVIDENCE':ev if ev else '','LOGICAL_CALL_CLOSED':resolution=='UNKNOWN',
                     'TIME':datetime.now(timezone.utc).isoformat()}
            self.db.execute('UPDATE calls SET state=?,cost=?,error=? WHERE key=?',(new,cost,'reconciled: '+resolution,key))
            self.event('CALL_RECONCILED',payload)
        return payload

    def record_candidate(self,cid,round_slot,call_key,contract,state,card,reasons):
        """Idempotent intake record. The same slot must always resolve the same way."""
        self._writable()
        if state not in CANDIDATE_STATES:raise ContractError('candidate state')
        row=(round_slot,call_key,contract,state,canonical(card) if card is not None else None,canonical(reasons))
        with self.transaction():
            old=self.db.execute('SELECT round,call_key,contract,state,card,reasons FROM candidates WHERE id=?',(cid,)).fetchone()
            if old is None:
                self.db.execute('INSERT INTO candidates VALUES (?,?,?,?,?,?,?)',(cid,)+row)
            elif old[:3]!=row[:3] or old[4]!=row[4] or (old[3] in ('VALID','HARD_FAIL') and (old[3],old[5])!=(state,row[5])):
                raise ContractError('intake record differs on replay for '+str(cid))

    def set_candidate_review(self,cid,state,reasons):
        self._writable()
        if state not in ('REVIEWED','REVIEW_FAILED'):raise ContractError('review state')
        with self.transaction():
            old=self.db.execute('SELECT state FROM candidates WHERE id=?',(cid,)).fetchone()
            if old is None or old[0] not in ('VALID','REVIEWED','REVIEW_FAILED'):raise ContractError('review of non-valid candidate')
            self.db.execute('UPDATE candidates SET state=?,reasons=? WHERE id=?',(state,canonical(reasons),cid))

    def candidates(self):
        return [{'CANDIDATE_ID':i,'ROUND':r,'CALL_KEY':k,'CONTRACT':c,'STATE':s,'CARD':json.loads(card) if card else None,'REASONS':json.loads(reasons)}
                for i,r,k,c,s,card,reasons in self.db.execute('SELECT id,round,call_key,contract,state,card,reasons FROM candidates ORDER BY id')]

    def export_calls(self):
        result=[]
        for key,request,state,reserved,response,cost,usage,error in self.db.execute('SELECT * FROM calls ORDER BY rowid'):
            req=json.loads(request);resp=json.loads(response) if response else None
            result.append({'CALL_KEY':key,'RUN_ID':self.get('config')['RUN_ID'],'PROMPT_VERSION':req.get('prompt_version'),'CONTEXT_DIGEST':digest(req.get('context')),'MODEL_PROVIDER':req.get('provider'),'MODEL_ID':req.get('model'),'MODEL_PARAMETERS':req.get('parameters'),'MODEL_REQUEST_PARAMS':req.get('model_request_params'),'SLOT':req.get('slot'),'CONTENT_ATTEMPT':req.get('content_attempt',0),'TRANSPORT_ATTEMPT':req.get('transport_attempt',0),'RAW_RESPONSE_SHA256':(resp or {}).get('raw_sha256') if resp else None,'WIRE_SHA256':(resp or {}).get('wire_sha256') if resp else None,'RESPONSE_ID':(resp or {}).get('response_id') if resp else None,'PROVIDER_STATUS':(resp or {}).get('provider_status') if resp else None,'COST_BASIS':(resp or {}).get('COST_BASIS') if resp else None,'STATE':state,'RESERVED_MICRO_USD':reserved,'COST_MICRO_USD':cost,'USAGE':json.loads(usage) if usage else None,'ERROR':error,'SOURCE_RUN_ID':(resp or {}).get('SOURCE_RUN_ID') if resp else None,'SOURCE_CALL_KEY':(resp or {}).get('SOURCE_CALL_KEY') if resp else None,'SOURCE_RESPONSE_ID':(resp or {}).get('SOURCE_RESPONSE_ID') if resp else None,'SOURCE_RAW_RESPONSE_SHA256':(resp or {}).get('SOURCE_RAW_RESPONSE_SHA256') if resp else None})
        return result

    def save_card(self,card,decision=None):
        self._writable()
        self.db.execute('INSERT INTO cards VALUES (?,?,?)',(card['CANDIDATE_ID'],canonical(card),canonical(decision)))

    def event(self,kind,payload):
        self._writable()
        self.db.execute('INSERT INTO events(kind,payload) VALUES (?,?)',(kind,canonical(payload)))

    def mutate(self,card_id,field,after,reason,actor,validate):
        self._writable()
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
