"""Card admissibility, provider/app output schemas and normalization.

Card rules live in contract.py (GENERATOR_CONTRACT_V02). Historical v0.1 cards
are admitted only through legacy_v01.py (exact grandfathered digests).
"""
import json
import math
import re
from .context import ContractError, digest
from . import contract
from .contract import DATA_FIELDS, TEXT_FIELDS, text, LEGAL_RANGE_PATTERN

def parse_json(raw):
    def pairs(items):
        d={}
        for key,value in items:
            if key in d:raise ContractError('duplicate JSON key')
            d[key]=value
        return d
    try:
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ContractError('nonfinite JSON')))
    except (ValueError,TypeError) as e:
        raise ContractError('malformed JSON') from e

def validate_card(card, contexts):
    """Admissible card: GENERATOR_CONTRACT_V02, or an exact grandfathered v0.1 card.

    Intake of generated rounds uses contract.card_violations (per-card
    quarantine) or legacy_v01.admit_card (call-key bound). This function is the
    downstream re-check used by critics, context validation and human mutation.
    """
    from . import legacy_v01
    if legacy_v01.admitted_by_digest(card,contexts):return card
    return contract.validate_card_v02(card,contexts)

def signature(card):
    return digest({k:card[k] for k in ('MECHANISM','INFORMATION_SOURCE','OBSERVABLE','FUNCTION','PRIMARY_TARGET','HORIZON')})

def strict_object(properties):
    props=dict(properties)
    return {'type':'object','properties':props,'required':sorted(props),'additionalProperties':False}

def search_surface_application_schema():
    # Dynamic parameter names remain a dict for the frozen application card.
    return strict_object({'MAX_VARIANTS':{'type':'integer','minimum':1,'maximum':100},'PARAMETERS':{'type':'object','properties':{},'required':[],'additionalProperties':True}})

def search_surface_provider_schema():
    # Strict JSON Schema forbids free-form object keys. Encode the frozen
    # PARAMETERS dict as an array of {NAME,VALUES} without changing card semantics.
    value={'anyOf':[{'type':'string'},{'type':'integer'},{'type':'number'}]}
    entry=strict_object({'NAME':{'type':'string'},'VALUES':{'type':'array','minItems':1,'items':value}})
    return strict_object({'MAX_VARIANTS':{'type':'integer','minimum':1,'maximum':100},'PARAMETERS':{'type':'array','minItems':1,'items':entry}})

def output_schema(contexts,*,provider=False,slot=None):
    """One V02 card. With a slot, identity fields are pinned to one-value enums."""
    d=contexts.design
    taxonomy=sorted(d['DATA_STATUS_TAXONOMY'])
    props={k:{'type':'string'} for k in d['CANDIDATE_SCHEMA']['REQUIRED_FIELDS']}
    props['CANDIDATE_ID']={'type':'string','pattern':r'^C[0-9]{3}$'}
    props['MECHANISM_FAMILY']={'type':'string','enum':sorted(set(contexts.families)|{'NEW_FAMILY_PROPOSAL'})}
    if slot is not None:
        props['CANDIDATE_ID']={'type':'string','enum':[slot['CANDIDATE_ID']]}
        props['MECHANISM_FAMILY']={'type':'string','enum':[slot['MECHANISM_FAMILY']]}
        props['INFORMATION_SOURCE']={'type':'string','enum':[slot['INFORMATION_SOURCE']]}
    props['PROTECTED_DATA_REQUIREMENT']={'type':'boolean','enum':[False]}
    props['DATA_STATUS']={'type':'string','enum':taxonomy}
    props['NEAREST_TESTED_MECHANISM']={'type':'string','enum':contract.nearest_mechanism_ids(contexts)}
    props['MISSING_OBSERVABLES']={'type':'array','items':{'type':'string'}}
    row={'DATASET':{'type':'string'},'OBSERVABLE':{'type':'string'},'STATUS':{'type':'string','enum':taxonomy},
         'LEGAL_RANGE':{'type':'string','pattern':LEGAL_RANGE_PATTERN}}
    props['DATA_REQUIRED']={'type':'array','minItems':1,'maxItems':contract.MAX_DATA_ROWS,'items':strict_object(row)}
    props['SEARCH_SURFACE']=search_surface_provider_schema() if provider else search_surface_application_schema()
    return strict_object(props)

def normalize_search_surface(surface):
    if not isinstance(surface,dict):raise ContractError('search surface shape')
    params=surface.get('PARAMETERS')
    if isinstance(params,list):
        converted={}
        for row in params:
            if not isinstance(row,dict) or set(row)!={'NAME','VALUES'}:raise ContractError('provider search-surface encoding')
            name=row['NAME']
            if not isinstance(name,str) or name in converted:raise ContractError('duplicate search parameter')
            converted[name]=row['VALUES']
        surface={**surface,'PARAMETERS':converted}
    return surface

def _keyed_relations(value,key):
    if isinstance(value,dict):
        return [{key:k,'RELATION':v} for k,v in sorted(value.items())]
    return value

def normalize_role_output(role,payload):
    """Provider encodings -> application form. Does not judge content."""
    if not isinstance(payload,dict):return payload
    if role=='GENERATOR':
        cands=payload.get('CANDIDATES')
        if isinstance(cands,dict):
            cands=[dict(v,CANDIDATE_ID=v.get('CANDIDATE_ID',k)) if isinstance(v,dict) else v for k,v in sorted(cands.items())]
        if not isinstance(cands,list):return payload
        cards=[]
        for card in cands:
            if isinstance(card,dict) and isinstance(card.get('SEARCH_SURFACE'),dict):
                try:card={**card,'SEARCH_SURFACE':normalize_search_surface(card['SEARCH_SURFACE'])}
                except ContractError:pass
            cards.append(card)
        return {**payload,'CANDIDATES':cards}
    if role=='NOVELTY_CRITIC':
        out=dict(payload)
        if 'PRIOR_RELATIONS' in out:out['PRIOR_RELATIONS']=_keyed_relations(out['PRIOR_RELATIONS'],'SIGNATURE_ID')
        if 'BATCH_RELATIONS' in out:out['BATCH_RELATIONS']=_keyed_relations(out['BATCH_RELATIONS'],'CANDIDATE_ID')
        return out
    return payload

def validate_instance(instance,schema):
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try:validate_instance(instance,option);return
            except ContractError:pass
        raise ContractError('anyOf failed')
    expected=schema.get('type')
    if expected=='object':
        if not isinstance(instance,dict):raise ContractError('expected object')
        additional=schema.get('additionalProperties')
        required=list(schema.get('required',[]))
        props=dict(schema.get('properties',{}))
        if additional is False:
            if set(required)!=set(props):raise ContractError('schema required must list every property')
            extra=set(instance)-set(props);missing=set(props)-set(instance)
            if extra or missing:raise ContractError('object fields differ from schema')
        elif additional is True:
            missing=[k for k in required if k not in instance]
            if missing:raise ContractError('object fields differ from schema')
        else:
            raise ContractError('schema must set additionalProperties')
        for key,sub in props.items():
            if key in instance:validate_instance(instance[key],sub)
        return
    if expected=='array':
        if not isinstance(instance,list):raise ContractError('expected array')
        lo,hi=schema.get('minItems'),schema.get('maxItems')
        if lo is not None and len(instance)<lo:raise ContractError('array too short')
        if hi is not None and len(instance)>hi:raise ContractError('array too long')
        item=schema.get('items')
        if item is None:raise ContractError('array items required')
        for value in instance:validate_instance(value,item)
        return
    if expected=='string':
        if not isinstance(instance,str):raise ContractError('expected string')
        if 'enum' in schema and instance not in schema['enum']:raise ContractError('string enum')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'],instance):raise ContractError('string pattern')
        return
    if expected=='boolean':
        if type(instance) is not bool:raise ContractError('expected boolean')
        if 'enum' in schema and instance not in schema['enum']:raise ContractError('boolean enum')
        return
    if expected=='integer':
        if type(instance) is not int:raise ContractError('expected integer')
        if instance<schema.get('minimum',instance) or instance>schema.get('maximum',instance):raise ContractError('integer range')
        return
    if expected=='number':
        if type(instance) not in (int,float) or type(instance) is bool:raise ContractError('expected number')
        if isinstance(instance,float) and not math.isfinite(instance):raise ContractError('nonfinite number')
        return
    raise ContractError('unsupported schema type')
