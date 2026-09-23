import json
import pytest
from scripts.research.generator_v0.__main__ import main
from scripts.research.generator_v0.context import ContractError
from scripts.research.generator_v0.ledger import Ledger

def test_operator_cli_run_review_mutation(tmp_path,capsys):
    dest=str(tmp_path/'run')
    main(['run','--run-dir',dest]);main(['resume','--run-dir',dest])
    main(['review','--run-dir',dest,'--candidate-id','C006','--decision','DEFER','--reason','verify definition','--actor','owner','--active-minutes','3'])
    main(['mutate','--run-dir',dest,'--candidate-id','C006','--field','NAME','--value-json','"New name"','--reason','clarify','--actor','owner'])
    l=Ledger(tmp_path/'run/run.sqlite');assert l.get('status')=='MUTATED_REQUIRES_REVIEW'
    assert l.db.execute("SELECT count(*) FROM events WHERE kind='HUMAN_MUTATION'").fetchone()[0]==1
    with pytest.raises(ContractError):main(['resume','--run-dir',dest])
    main(['inspect','--run-dir',dest]);assert 'New name' in capsys.readouterr().out

def test_no_credential_required_for_mock(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False);main(['preflight'])
    with pytest.raises(ContractError):main(['preflight','--provider','openai','--allow-real-llm','--budget-usd','30'])
