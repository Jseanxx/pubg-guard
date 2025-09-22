# guard/state.py
import asyncio, hashlib
from dataclasses import dataclass, field
from typing import Optional
from time import time as _now

class TTLSet:
    def __init__(self, ttl_sec: int):
        self.ttl = ttl_sec
        self.store: dict[object, float] = {}
    def add(self, key: object):
        self.store[key] = _now() + self.ttl
    def contains(self, key: object) -> bool:
        exp = self.store.get(key)
        if not exp: return False
        if exp < _now():
            self.store.pop(key, None)
            return False
        return True
    def gc(self):
        now = _now()
        for k, exp in list(self.store.items()):
            if exp < now: self.store.pop(k, None)

@dataclass
class Caches:
    msg_ttl: TTLSet = field(default_factory=lambda: TTLSet(20*60))
    att_ttl: TTLSet = field(default_factory=lambda: TTLSet(20*60))
    recent_text_hash: TTLSet = field(default_factory=lambda: TTLSet(10*60))  # 반복/크로스포스트
    last_avatar_key: dict[int, Optional[str]] = field(default_factory=dict)
    suspect_by_avatar: set[int] = field(default_factory=set)
    first_msg_seen: set[int] = field(default_factory=set)

@dataclass
class Counters:
    hour_avatar: int = 0
    hour_message: int = 0
    hour_enforce: int = 0

@dataclass
class Concurrency:
    qr_sem: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(2))
    phash_sem: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(3))

@dataclass
class State:
    caches: Caches
    counters: Counters
    conc: Concurrency

def init_state(qr_sem_size: int, phash_sem_size: int) -> State:
    return State(
        caches=Caches(),
        counters=Counters(),
        conc=Concurrency(
            qr_sem=asyncio.Semaphore(qr_sem_size),
            phash_sem=asyncio.Semaphore(phash_sem_size),
        ),
    )

def norm_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()
