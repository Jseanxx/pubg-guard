# guard/types.py
from dataclasses import dataclass
from typing import Optional, Literal, List
from datetime import datetime

EventKind = Literal["QR", "AVATAR", "MESSAGE"]
Tier = Optional[Literal["STRICT", "NORMAL"]]

@dataclass
class LogPayload:
    guild_id: int
    user_id: int
    mention: str
    channel_mention: Optional[str] = None
    created_at_utc: Optional[datetime] = None
    joined_at_utc: Optional[datetime] = None
    avatar_url_256: Optional[str] = None
    # QR
    qr_text_obfuscated: Optional[str] = None
    policy_effect: Optional[str] = None
    # MESSAGE/AVATAR
    tier: Tier = None
    score: Optional[int] = None
    score_threshold: Optional[int] = None
    reasons: Optional[List[str]] = None
    hits: Optional[List[str]] = None
    preview: Optional[str] = None
    jump_url: Optional[str] = None
