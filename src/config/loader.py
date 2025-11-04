from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"

def load_thresholds(path: str | None = None):
    """thresholds.json を読み込む（デフォルトは config/thresholds/thresholds.json）。"""
    p = Path(path) if path else CONFIG_DIR / "thresholds" / "thresholds.json"
    return json.loads(p.read_text(encoding="utf-8"))

def get_versions(*args, **kwargs):
    """required_versions.json があれば拾い、無ければ unknown を返す。
    *args, **kwargs を受けておくことで Streamlit コールバック経由でも安全。
    """
    rv = CONFIG_DIR / "required_versions.json"
    if rv.exists():
        data = json.loads(rv.read_text(encoding="utf-8"))
        return {
            "thresholds_json": data.get("thresholds_json", "unknown"),
            "scoring_engine":  data.get("scoring_engine",  "unknown"),
            "dashboard":       data.get("dashboard",       "unknown"),
        }
    return {
        "thresholds_json": "unknown",
        "scoring_engine": "unknown",
        "dashboard": "unknown"
    }
