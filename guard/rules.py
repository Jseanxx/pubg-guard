# guard/rules.py
import json, os
from typing import Any

class Rules:
    def __init__(self, data: dict[str, Any]):
        self.data = data or {}

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    @property
    def keywords(self) -> dict: return self.data.get("keywords", {})
    @property
    def homoglyphs(self) -> dict: return self.data.get("homoglyphs", {})
    @property
    def sensitivity(self) -> dict: return self.data.get("sensitivity", {})
    @property
    def policy(self) -> dict: return self.data.get("policy", {})
    @property
    def nick_flags(self) -> list[str]: return self.data.get("nick_flags", [])
    @property
    def negations(self) -> list[str]: return self.data.get("negations", [])
    @property
    def repeat_window_sec(self) -> int: return int(self.data.get("repeat_window_sec", 600))

def load_rules(path: str) -> Rules:
    if not os.path.exists(path):
        raise SystemExit(f"rules.json 필요: {path} 없음")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Rules(data)
