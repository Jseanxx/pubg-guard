# guard/policy.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
import discord

from .schemas import EventKind, Tier
from .config import Config
from .state import State

log = logging.getLogger("guard.policy")
UTC = timezone.utc
def now_utc() -> datetime: return datetime.now(UTC)

async def _resolve_member(msg: discord.Message) -> Optional[discord.Member]:
    if isinstance(msg.author, discord.Member):
        return msg.author
    if msg.guild:
        try:
            m = msg.guild.get_member(msg.author.id)
            if m: return m
            return await msg.guild.fetch_member(msg.author.id)
        except Exception:
            return None
    return None

async def apply_policy(
    kind: EventKind, msg: discord.Message, tier: Tier, cfg: Config, state: State
) -> str:
    # 1) 액션 결정
    action = {
        "QR": cfg.policy_qr,
        "MESSAGE": cfg.policy_message,
        "AVATAR": cfg.policy_avatar,
    }[kind]

    effect_delete = False
    effect_timeout = False
    effect_ban = False

    # 2) 삭제 (delete / delete_timeout)
    if action in ("delete", "delete_timeout"):
        try:
            await msg.delete()
            effect_delete = True
        except Exception as e:
            log.warning("메시지 삭제 실패: %s", e)

    # 3) Ban (우선순위: STRICT/MESSAGE, QR 스위치)
    try:
        do_ban = False
        if kind == "MESSAGE" and (tier == "STRICT") and cfg.ban_on_strict:
            do_ban = True
        elif kind == "QR" and cfg.ban_on_qr:
            do_ban = True
        elif kind == "MESSAGE" and (tier == "NORMAL") and cfg.ban_on_normal:
            do_ban = True

        if do_ban:
            member = await _resolve_member(msg)
            if member:
                await member.ban(reason=f"Automated ban by rules ({kind}{'/' + str(tier) if tier else ''})")
                effect_ban = True
            else:
                log.warning("밴 스킵: 멤버 조회 실패 uid=%s", getattr(msg.author, "id", "?"))
    except Exception as e:
        log.warning("밴 실패: %s", e)

    # 4) Timeout (timeout / delete_timeout) — 이미 Ban이면 스킵
    if (not effect_ban) and action in ("timeout", "delete_timeout"):
        try:
            member = await _resolve_member(msg)
            if member:
                until = now_utc() + timedelta(hours=cfg.timeout_hours)
                await member.edit(timed_out_until=until)
                effect_timeout = True
            else:
                log.warning("타임아웃 스킵: 멤버 조회 실패 uid=%s mid=%s",
                            getattr(msg.author, "id", "?"), getattr(msg, "id", "?"))
        except Exception as e:
            log.warning("타임아웃 실패: %s", e)

    # 5) 카운터
    if effect_delete or effect_timeout or effect_ban:
        state.counters.hour_enforce += 1

    # 6) 결과 문자열
    if effect_ban and effect_delete: return "Ban + Delete"
    if effect_ban: return "Ban"
    if effect_timeout and effect_delete: return f"Timeout ({cfg.timeout_hours}h) + Delete"
    if effect_timeout: return f"Timeout ({cfg.timeout_hours}h)"
    if effect_delete: return "Delete"
    return "None"
