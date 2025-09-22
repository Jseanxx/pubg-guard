# guard/detectors/message.py
import re
import unicodedata
from typing import List, Tuple

from .rules import Rules

ZERO_WIDTH = re.compile(r"[\u200B\u200C\u200D\u2060\uFEFF]")
NONWORD    = re.compile(r"[^0-9A-Za-z가-힣]+")
SEP_RUNS   = re.compile(r"[ \t\n\r\-\._/\\|·•‧∙・,、，:;]+")

def normalize(text: str, rules: Rules) -> Tuple[str, str]:
    """return (s_norm, condensed)"""
    homo = rules.homoglyphs or {}
    s = text or ""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(str.maketrans(homo))
    s = ZERO_WIDTH.sub("", s)
    s = s.lower()
    condensed = NONWORD.sub("", s)
    return s, condensed

def near_hits(condensed: str, A: List[str], B: List[str], win: int):
    a_hits, b_hits = [], []
    for a in (A or []):
        i = condensed.find(a)
        if i == -1:
            continue
        seg = condensed[i + len(a): i + len(a) + win]
        for b in (B or []):
            if b in seg:
                a_hits.append(a); b_hits.append(b)
                break
    if a_hits and b_hits:
        # uniq (order-preserve)
        ah = list(dict.fromkeys(a_hits))
        bh = list(dict.fromkeys(b_hits))
        return True, ah, bh
    return False, [], []

def score_message(content: str, rules: Rules):
    s, condensed = normalize(content, rules)
    k = rules.keywords or {}
    w = (rules.get("weights") or {})
    sens = rules.sensitivity or {}

    score, reasons, hits = 0, [], []

    ok, ah, bh = near_hits(condensed, k.get("profile", []), k.get("visit", []), int(sens.get("near_window", 12)))
    if ok:
        score += int(w.get("profile_visit", 40)); reasons.append("프로필+방문"); hits += ah + bh

    reward_terms = [x for x in (k.get("reward", []) or []) if x in condensed]
    if reward_terms:
        score += int(w.get("reward", 25)); reasons.append("보상/수령/이벤트"); hits += reward_terms

    gcoin_terms = [x for x in (k.get("gcoin", []) or []) if x in condensed]
    if gcoin_terms:
        score += int(w.get("gcoin", 25)); reasons.append("G-COIN"); hits += gcoin_terms

    # uniq (order-preserve)
    hits = list(dict.fromkeys(hits))
    return score, reasons, hits, s

def has_any_keyword(content: str, rules: Rules) -> bool:
    score, reasons, hits, _ = score_message(content, rules)
    return bool(reasons or hits)

def profile_visit_in_reasons(reasons: List[str]) -> bool:
    return "프로필+방문" in (reasons or [])

def nick_flag(display_name: str, rules: Rules) -> bool:
    _, condensed = normalize(display_name or "", rules)
    for key in (rules.nick_flags or []):
        k = (key or "").strip().lower()
        if not k: continue
        if k in condensed:
            return True
    return False

def negation_guard(content: str, hit_terms: List[str], rules: Rules, window: int = 20) -> bool:
    """
    키워드 근처(±window)에 부정/경고 표현이 있으면 True(=면책).
    간단히: 정규화된 본문 s에서 각 hit 주변 ±window 슬라이스에 negation 토큰 존재 여부.
    """
    negs = [n for n in (rules.negations or []) if n]
    if not negs or not hit_terms:
        return False
    s, _ = normalize(content or "", rules)
    s_len = len(s)
    # 슬라이스 검사를 위해 hit_terms도 정규화
    hit_norms = [normalize(h, rules)[0] for h in hit_terms]
    for h in hit_norms:
        i = s.find(h)
        if i == -1: 
            continue
        left = max(0, i - window)
        right = min(s_len, i + len(h) + window)
        zone = s[left:right]
        for n in negs:
            n_norm = normalize(n, rules)[0]
            if n_norm and n_norm in zone:
                return True
    return False

def text_signature(content: str, rules: Rules) -> str:
    """반복/크로스포스트 탐지용: 정규화(condensed) 기반 서명 문자열"""
    _, condensed = normalize(content or "", rules)
    return condensed[:256]  # 너무 길면 잘라서 키로
