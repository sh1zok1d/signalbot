"""Frozen source projections and role boundaries. Only metadata files are read."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESIGN = 'docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.json'
MEMORY = 'docs/research/MECHANISM_MEMORY_V0.json'
ROTATION = 'docs/research/HETEROGENEOUS_FAMILY_ROTATION_V3.json'
MAP = 'docs/research/BLIND_MECHANISM_MAP_V0.json'
AUTHORITY = 'docs/research/GOVERNANCE_REGION_AUTHORITY_V0.json'
PINS = 'docs/research/GENERATOR_V0_CONTEXT_PINS.json'

class ContractError(ValueError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def byte_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')

def project(memory, design):
    blind = design['BLIND_GENERATOR_CONTEXT']
    out = {}
    for key, entry in memory['ENTRIES'].items():
        row = {field: entry[field] for field in blind['WHITELISTED_FIELDS']}
        for target, value in blind['SANITIZATION_OVERRIDES'].items():
            card, field = target.split('.', 1)
            if card == key:
                row[field] = value
        row['REGION_STATE'] = 'PRIOR_WORK_SIGNATURE'
        out[key] = row
    return out

def materialize(root=ROOT):
    """Explicit developer operation. Runtime never regenerates trusted projections."""
    design = read(root/DESIGN)
    write_json(root/MAP, project(read(root/MEMORY), design))
    write_json(root/AUTHORITY, design['GOVERNANCE_REGION_AUTHORITY_V0'])
    write_json(root/PINS, {p: byte_digest(root/p) for p in (DESIGN, MEMORY, ROTATION, MAP, AUTHORITY)})

class Contexts:
    def __init__(self, root=ROOT):
        self.root = root
        self.verify()
        self.design = read(root/DESIGN)
        self.blind = read(root/MAP)
        self.authority = read(root/AUTHORITY)
        self.catalog = {k: {f: v.get(f) for f in ('CONTENT','LEGAL_RANGE','STATUS')}
                        for k,v in self.design['DATA_CATALOG_V0_SEED'].items()}
        self.families = {k:v['NAME'] for k,v in read(root/ROTATION)['FAMILY_STATUS'].items()}
        self.rows = {}
        for row in self.authority['ROWS']:
            self.rows[row['SIGNATURE_ID']] = row
            for sub in row.get('SUB_SIGNATURES', []):
                self.rows[sub['SIGNATURE_ID']] = sub
        if set(self.blind) != {r['SIGNATURE_ID'] for r in self.authority['ROWS']}:
            raise ContractError('authority coverage')

    def verify(self):
        pins = read(self.root/PINS)
        if set(pins) != {DESIGN,MEMORY,ROTATION,MAP,AUTHORITY}:
            raise ContractError('pin manifest shape')
        for path, expected in pins.items():
            if byte_digest(self.root/path) != expected:
                raise ContractError('source drift: '+path)
        d = read(self.root/DESIGN)
        if read(self.root/MAP) != project(read(self.root/MEMORY), d):
            raise ContractError('blind map projection mismatch')
        if read(self.root/AUTHORITY) != d['GOVERNANCE_REGION_AUTHORITY_V0']:
            raise ContractError('authority differs from design')

    def scan(self, value):
        pattern = self.design['BLIND_GENERATOR_CONTEXT']['CONTEXT_SCANNER']['DENYLIST_REGEX']
        if re.search(pattern, canonical(value), re.I):
            raise ContractError('generator context scanner hit')

    def generator(self):
        self.verify()
        return copy.deepcopy({
            'BLIND_MECHANISM_MAP_V0': self.blind,
            'DATA_CATALOG_V0': self.catalog,
            'CANDIDATE_SCHEMA': self.design['CANDIDATE_SCHEMA'],
            'DATA_STATUS_TAXONOMY': self.design['DATA_STATUS_TAXONOMY'],
            'GENERIC_METHODOLOGY': {
                'FAMILY_TAXONOMY': self.families,
                'METHODOLOGY': self.design['GENERIC_METHODOLOGY_LESSONS'],
                'GENERATOR_SIDE_RULE': self.design['BLIND_GENERATOR_CONTEXT']['GENERATOR_SIDE_RULE'],
            },
        })

    def provenance(self):
        # Output paths are bundled by role, but each source/transform/output identity
        # remains exactly the reviewed allowlist. No arbitrary caller provenance.
        return copy.deepcopy(self.design['BLIND_GENERATOR_CONTEXT']['STRUCTURAL_PROVENANCE_GUARD']['FIELD_ALLOWLIST'])

    def validate(self, role, context, prompt=''):
        self.verify()
        matrix = self.design['ROLE_CONTEXT_MATRIX'].get(role)
        if role == 'HUMAN' or matrix is None:
            raise ContractError('not an automated role')
        allowed = set(matrix['ALLOWED']) | set(matrix['CONDITIONAL'])
        if set(context) - allowed:
            raise ContractError('forbidden role context')
        if role == 'GENERATOR':
            if context != self.generator():
                raise ContractError('generator context has noncanonical provenance')
            self.scan({'context':context, 'prompt':prompt})
        elif role == 'RED_TEAM' and 'GOVERNANCE_REGION_AUTHORITY_V0' in context:
            rows = context['GOVERNANCE_REGION_AUTHORITY_V0']
            cited = context.get('CANDIDATE',{}).get('NEAREST_TESTED_MECHANISM')
            if not isinstance(rows,list) or len(rows)!=1 or rows[0] != self.rows.get(cited):
                raise ContractError('unscoped governance access')
