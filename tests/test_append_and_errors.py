import json, os, io, pytest, tempfile, builtins
from tests._contract_loader import load_impl_from_contract, fixtures

def _read_all(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def test_append_is_not_truncating_and_creates_file(tmp_path):
    contract, func = load_impl_from_contract()

    # 既存1行 → 追記で2行
    p = tmp_path / "data.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"pre":1}\n')
    func(str(p), {"a": 2})
    rows = _read_all(p)
    assert rows[0]["pre"] == 1
    assert rows[1]["a"] == 2

    # 未存在 → 作成され1行
    q = tmp_path / "new.jsonl"
    func(str(q), {"x": 9})
    rows2 = _read_all(q)
    assert rows2 == [{"x": 9}]
    # 改行終端
    with open(q, "rb") as f:
        assert f.read().endswith(b"\n")

def test_invalid_path_raises(monkeypatch, tmp_path):
    # OS依存の/rootはCIで不安定なので、openをPermissionErrorに差し替え
    contract, func = load_impl_from_contract()

    real_open = builtins.open
    def deny_open(*args, **kwargs):
        raise PermissionError("denied")
    monkeypatch.setattr(builtins, "open", deny_open)

    try:
        with pytest.raises(Exception):
            func("/root/blocked.jsonl", {"a": 1})
    finally:
        monkeypatch.setattr(builtins, "open", real_open)
