"""Human actions record intent only. They never authorize scientific execution."""
import json
import math
from .context import ContractError
from .schema import validate_card

def human_events(ledger):
    return [{'KIND':kind,'PAYLOAD':json.loads(payload)} for kind,payload in ledger.db.execute("SELECT kind,payload FROM events WHERE kind LIKE 'HUMAN_%' ORDER BY n")]

def adjudicate(ledger,candidate_id,decision,reason,actor,minutes):
    if not reason or not reason.strip() or not actor or not actor.strip():raise ContractError('actor and reason required')
    if decision not in ('ACCEPT_FOR_FUTURE_DESIGN','REJECT','DEFER'):raise ContractError('review decision')
    if not math.isfinite(minutes) or minutes<0:raise ContractError('human active minutes')
    with ledger.transaction():
        if not ledger.db.execute('SELECT 1 FROM cards WHERE id=?',(candidate_id,)).fetchone():raise ContractError('unknown candidate')
        ledger.event('HUMAN_REVIEW',{'CANDIDATE_ID':candidate_id,'DECISION':decision,'REASON':reason,'ACTOR':actor,'ACTIVE_MINUTES':minutes})

def registry(ledger):
    # Read authority, not editable JSON report files.
    cards=[{'CARD':json.loads(card),'REVIEW':json.loads(review) if review else None} for card,review in ledger.db.execute('SELECT card,decision FROM cards ORDER BY id')]
    return {'STATUS':ledger.get('status'),'CARDS':cards,'HUMAN_EVENTS':human_events(ledger)}
