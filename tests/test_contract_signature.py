import inspect
from tests._contract_loader import load_impl_from_contract

def test_signature_matches_contract():
    contract, func = load_impl_from_contract()
    sig = inspect.signature(func)
    assert list(sig.parameters.keys()) == ["path", "record"], "引数は(path, record)の順を必須"
    # None or no annotation both acceptable (inspect._empty means no annotation)
    assert sig.return_annotation in (None, type(None), inspect._empty), "戻り値はNone注釈が望ましい"
