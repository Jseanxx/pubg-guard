# guard/handlers/members.py
import logging
from datetime import datetime, timezone

import discord

from ..config import Config
from ..rules import Rules
from ..state import State
from ..detectors.avatar import scan_avatar_event

log = logging.getLogger("guard.handlers.members")
UTC = timezone.utc
def now_utc(): return datetime.now(UTC)

async def handle_member_join(cfg: Config, rules: Rules, state: State, m: discord.Member):
    # 베이스라인 key 저장 + 이벤트 스캔 1회
    try:
        state.caches.last_avatar_key[m.id] = getattr(m.display_avatar, "key", None)
    except Exception:
        pass
    try:
        await scan_avatar_event(m, cfg, state)
    except Exception as e:
        log.warning("scan_avatar_event(join) 실패: %s", e)

async def handle_member_update(cfg: Config, rules: Rules, state: State, before: discord.Member, after: discord.Member):
    # key 변화 시 이벤트 스캔
    try:
        before_k = getattr(before.display_avatar, "key", None)
        after_k  = getattr(after.display_avatar, "key", None)
        if before_k != after_k:
            await scan_avatar_event(after, cfg, state)
    except Exception as e:
        log.warning("scan_avatar_event(update) 실패: %s", e)

async def handle_user_update(cfg: Config, rules: Rules, state: State, client: discord.Client, before: discord.User, after: discord.User):
    # guild 멤버 객체 확보 후 이벤트 스캔
    try:
        # 여러 길드 중 하나만 — 주요 길드
        g = client.get_guild(int(cfg.guild_id))
        if not g: return
        m = g.get_member(after.id) or await g.fetch_member(after.id)
        await scan_avatar_event(m, cfg, state)
    except Exception:
        pass
