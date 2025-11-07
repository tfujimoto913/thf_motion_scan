# 契約YAMLから実装関数を解決する互換ローダ
# - impl: {module, symbol} があればそれを使う
# - implが無く module だけなら、moduleにappend_jsonlが居ればそれを使う
# - どちらにも居なければ、thresholds_editor.changelog.append_jsonl をフォールバック
import importlib, inspect, yaml, pathlib

CONTRACT_PATH = pathlib.Path("contracts/append_jsonl.yaml")

def _import(module_name, symbol_name):
    mod = importlib.import_module(module_name)
    try:
        return getattr(mod, symbol_name)
    except AttributeError as e:
        raise ImportError(f"symbol '{symbol_name}' not found in module '{module_name}'") from e

def load_impl_from_contract():
    with open(CONTRACT_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    c = data["contract"]

    # 1) 推奨: impl: {module, symbol}
    impl = c.get("impl")
    if impl and "module" in impl and "symbol" in impl:
        func = _import(impl["module"], impl["symbol"])
        return c, func

    # 2) Notion版: module のみ。append_jsonl という名前で探す。
    module_name = c.get("module")
    if module_name:
        try:
            func = _import(module_name, c["name"])
            return c, func
        except Exception:
            pass  # 次のフォールバックへ

    # 3) 最後の手段: 実リポ構成に合わせた既定位置
    func = _import("thresholds_editor.changelog", "append_jsonl")
    return c, func

def required_log_keys(contract):
    return contract["side_effects"]["logs"]["required_keys"]

def fixtures(contract):
    return {i["name"]: i for i in contract["fixtures"]}
