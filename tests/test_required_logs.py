import logging, os, json, tempfile
from tests._contract_loader import load_impl_from_contract, required_log_keys

def test_required_log_keys_emitted(caplog):
    contract, func = load_impl_from_contract()
    keys = required_log_keys(contract)
    with tempfile.TemporaryDirectory() as d, caplog.at_level(logging.INFO):
        p = os.path.join(d, "ok.jsonl")
        func(p, {"x": 1})
    # dictをlogging.infoに渡しても文字列化されるのでsubstringでチェック
    text = "\n".join(r.message for r in caplog.records)
    for k in keys:
        assert k in text, f"missing log key: {k}"
