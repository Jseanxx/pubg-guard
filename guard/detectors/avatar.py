# guard/detectors/avatar.py
import io, os, logging, asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple

import discord
from PIL import Image
import imagehash

from ..config import Config
from ..state import State

log = logging.getLogger("guard.detectors.avatar")
UTC = timezone.utc
def now_utc(): return datetime.now(UTC)

# 전역 레퍼런스 캐시
_REF_HASHES: List[Tuple[str, imagehash.ImageHash]] = []
_LOADED_DIR: Optional[str] = None

def load_refs(cfg: Config) -> int:
    """PHISH_DIR에서 참조 이미지(f.png 등) 로드 → pHash 리스트 생성"""
    global _REF_HASHES, _LOADED_DIR
    if _LOADED_DIR == cfg.phish_dir and _REF_HASHES:
        return len(_REF_HASHES)

    _REF_HASHES = []
    _LOADED_DIR = cfg.phish_dir
    if not os.path.isdir(cfg.phish_dir):
        log.info("레퍼런스 폴더 없음: %s", cfg.phish_dir)
        return 0

    cnt = 0
    for name in os.listdir(cfg.phish_dir):
        if not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        p = os.path.join(cfg.phish_dir, name)
        try:
            with Image.open(p) as im:
                h = imagehash.phash(im.convert("RGB").resize((256, 256)))
            _REF_HASHES.append((name, h))
            cnt += 1
        except Exception as e:
            log.warning("레퍼런스 로드 실패: %s (%s)", p, e)
    log.info("아바타 레퍼런스 해시 %d개 로드", cnt)
    return cnt

async def _avatar_bytes(asset: discord.Asset) -> Optional[bytes]:
    try:
        asset = asset.with_format("png").with_size(256)
        return await asset.read()
    except Exception as e:
        log.warning("아바타 다운로드 실패: %s", e)
        return None

async def _phash_bytes(b: bytes) -> imagehash.ImageHash:
    with Image.open(io.BytesIO(b)) as im:
        im = im.convert("RGB").resize((256, 256))
        return imagehash.phash(im)

def _min_dist(q: imagehash.ImageHash) -> Tuple[int, Optional[str]]:
    best = 999
    best_name = None
    for name, h in _REF_HASHES:
        d = int(q - h)
        if d < best:
            best = d; best_name = name
            if best == 0: break
    return best, best_name

def _cooldown_ok(state: State, uid: int, ttl_sec: int) -> bool:
    # TTLSet을 재사용하지 않고 간단한 맵/만료로 구현
    if not hasattr(state.caches, "phash_cd_map"):
        state.caches.phash_cd_map = {}  # type: ignore
        state.caches.phash_cd_exp = {}  # type: ignore
    now = datetime.now().timestamp()
    exp = state.caches.phash_cd_exp.get(uid, 0)     # type: ignore
    if exp > now:
        return False
    state.caches.phash_cd_exp[uid] = now + ttl_sec  # type: ignore
    return True

async def phash_on_demand(member: Optional[discord.Member], cfg: Config, state: State) -> bool:
    """
    키워드 히트 시에만 호출되는 온디맨드 검사.
    - 쿨다운: cfg.phash_cooldown_h
    - 동시성: state.conc.phash_sem
    - 캐시: state.caches.last_avatar_key
    return: 매치여부(True=STRICT 승격)
    """
    if not member or not member.display_avatar:
        return False
    if not _REF_HASHES:
        # 필요 시 동적 로드
        load_refs(cfg)
        if not _REF_HASHES:
            return False

    uid = member.id
    if not _cooldown_ok(state, uid, cfg.phash_cooldown_h * 3600):
        return False

    key = getattr(member.display_avatar, "key", None)
    # 동일 key면 최근에 확인했을 가능성 → 그래도 쿨다운 통과했으면 1회 검사 허용
    state.caches.last_avatar_key[uid] = key

    b = await _avatar_bytes(member.display_avatar)
    if not b:
        return False

    async with state.conc.phash_sem:
        try:
            q = await _phash_bytes(b)
        except Exception as e:
            log.warning("pHash 계산 실패: %s", e)
            return False

    dist, best_name = _min_dist(q)
    matched = dist <= cfg.phash_threshold
    if matched:
        state.caches.suspect_by_avatar.add(uid)
        log.info("pHash 매치: uid=%s best=%s d=%s", uid, best_name, dist)
    return matched

# --- 이벤트 기반 스캔(선택) -------------------------------------------------

async def scan_avatar_event(member: discord.Member, cfg: Config, state: State) -> bool:
    """
    조인≤window_days & key 변경 시 pHash 검사 (플래그만)
    """
    if not hasattr(member, "joined_at") or not member.joined_at:
        return False
    if (now_utc() - member.joined_at) > timedelta(days=cfg.window_days):
        return False

    key = getattr(member.display_avatar, "key", None)
    base = state.caches.last_avatar_key.get(member.id)
    if base is None:
        state.caches.last_avatar_key[member.id] = key
        return False
    if key == base:
        return False
    state.caches.last_avatar_key[member.id] = key

    # 쿨다운 무시(변경 이벤트는 즉시 1회 확인)
    if not _REF_HASHES:
        load_refs(cfg)
        if not _REF_HASHES:
            return False

    b = await _avatar_bytes(member.display_avatar)
    if not b:
        return False
    async with state.conc.phash_sem:
        try:
            q = await _phash_bytes(b)
        except Exception as e:
            log.warning("pHash 계산 실패(event): %s", e)
            return False

    dist, best_name = _min_dist(q)
    if dist <= cfg.phash_threshold:
        state.caches.suspect_by_avatar.add(member.id)
        log.info("이벤트 pHash 매치: uid=%s best=%s d=%s", member.id, best_name, dist)
        return True
    return False