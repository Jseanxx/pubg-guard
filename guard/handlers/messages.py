# guard/handlers/messages.py
import asyncio, hashlib, logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord

from ..types import LogPayload, EventKind, Tier
from ..config import Config
from ..rules import Rules
from ..state import State, norm_hash
from ..emit import emit
from ..policy import apply_policy
from ..detectors.message import (
    score_message, has_any_keyword, profile_visit_in_reasons,
    nick_flag, negation_guard, text_signature, normalize,
)

log = logging.getLogger("guard.handlers.messages")
UTC = timezone.utc
def now_utc() -> datetime: return datetime.now(UTC)

# --- helpers ---------------------------------------------------------------

def _channel_in_list(msg: discord.Message, ids: list[int]) -> bool:
    """채널 또는 포럼 쓰레드의 parent 기준 매칭"""
    if not ids:  # 비워두면 아무 채널도 허용 X (명시적 리스트 운영)
        return False
    ch = msg.channel
    if getattr(ch, "id", None) in ids:
        return True
    parent_id = getattr(getattr(ch, "parent", None), "id", None)
    return parent_id in ids

def _log_only_channel(msg: discord.Message, cfg: Config) -> bool:
    ids = cfg.msg_exempt_log_only_ids or []
    if not ids: return False
    ch = msg.channel
    if getattr(ch, "id", None) in ids: return True
    parent_id = getattr(getattr(ch, "parent", None), "id", None)
    return parent_id in ids

def _joined_within_days(m: Optional[discord.Member], days: int) -> bool:
    if not m or not getattr(m, "joined_at", None):
        return False
    return (now_utc() - m.joined_at) <= timedelta(days=days)

def _msg_fingerprint(msg: discord.Message) -> str:
    content = (msg.content or "").strip()
    att_ids = ",".join(str(a.id) for a in (msg.attachments or []))
    h = hashlib.sha1((content + "|" + att_ids).encode("utf-8", "ignore")).hexdigest()
    return f"{msg.id}:{h}"

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

# 반복/크로스포스트 트래커 (state.caches에 동적 필드로 저장)
def _bump_repeat(state: State, uid: int, sig: str, ch_id: int, window_sec: int) -> tuple[int, int]:
    """
    return (count, distinct_channels)
    """
    if not hasattr(state.caches, "repeat_map"):
        state.caches.repeat_map = {}  # type: ignore[attr-defined]
    if not hasattr(state.caches, "repeat_exp"):
        state.caches.repeat_exp = {}  # type: ignore[attr-defined]

    now = datetime.now().timestamp()
    key = (uid, sig)
    exp_at = state.caches.repeat_exp.get(key, 0)  # type: ignore[attr-defined]
    if exp_at < now:
        # reset window
        state.caches.repeat_map[key] = {"count": 0, "chs": set()}  # type: ignore[attr-defined]
        state.caches.repeat_exp[key] = now + window_sec             # type: ignore[attr-defined]

    rec = state.caches.repeat_map[key]                                # type: ignore[attr-defined]
    rec["count"] = int(rec.get("count", 0)) + 1
    chs: set[int] = rec.get("chs", set())
    chs.add(ch_id)
    rec["chs"] = chs
    state.caches.repeat_map[key] = rec                                # type: ignore[attr-defined]
    return rec["count"], len(chs)

# --- public entry ----------------------------------------------------------

async def handle_message(
    client: discord.Client, cfg: Config, rules: Rules, state: State, msg: discord.Message
):
    # 0) 기본 가드
    if not getattr(msg, "guild", None): return
    if msg.author.bot or msg.webhook_id is not None: return
    if not _channel_in_list(msg, cfg.channel_msg_monitor_ids): return

    # TTL 중복 방지
    fp = _msg_fingerprint(msg)
    if state.caches.msg_ttl.contains(fp): return
    state.caches.msg_ttl.add(fp)

    # 멤버 확보
    member = await _resolve_member(msg)

    # 1) 조인 ≤ WINDOW_DAYS (텍스트 정밀은 유저 신입만)
    if not _joined_within_days(member, cfg.window_days):
        # 지정 채널이지만 구 유저면 로그만(원한다면 완전 패스도 가능)
        return

    # 2) 키워드 프리필터(1개라도 히트? 없으면 종료)
    score, reasons, hits, s_norm = score_message(msg.content or "", rules)
    if not (reasons or hits):
        return

    # 2-1) 도움/프리채팅 면책(부정·경고 근접) — 포럼 쓰레드/프리채널 보호
    #  - 포럼(쓰레드)에는 면책 기본 적용
    is_thread = isinstance(msg.channel, discord.Thread)
    if is_thread or _log_only_channel(msg, cfg):
        if negation_guard(msg.content or "", hits or reasons, rules, window=20):
            # 로그만
            payload = LogPayload(
                guild_id=msg.guild.id,
                user_id=msg.author.id,
                mention=msg.author.mention,
                channel_mention=getattr(msg.channel, "mention", None),
                created_at_utc=msg.created_at or now_utc(),
                avatar_url_256=str(getattr(msg.author.display_avatar.with_size(256), "url", "")),
                tier=None,
                score=score,
                score_threshold=int(rules.sensitivity.get("msg_threshold_normal", 60)),
                reasons=reasons, hits=hits,
                preview=(msg.content or "").strip(),
                jump_url=getattr(msg, "jump_url", None),
                policy_effect="Log (negation-guard)",
            )
            await emit(client, cfg, "MESSAGE", payload)
            return

    # 3) STRICT 승격 트리거
    tier: Tier = None
    strict_due_to = None

    # 3-a) 닉네임 플래그 (“서포터즈” 유사)
    if nick_flag(getattr(member, "display_name", "") or getattr(msg.author, "display_name", ""), rules):
        tier = "STRICT"; strict_due_to = "nick-flag"

    # 3-b) profile_visit 조합
    if not tier and profile_visit_in_reasons(reasons):
        tier = "STRICT"; strict_due_to = "profile_visit"

    # 3-c) 반복/크로스포스트 (10분 내 2회 또는 다채널)
    if not tier:
        sig = text_signature(msg.content or "", rules)
        cnt, chs = _bump_repeat(state, msg.author.id, sig, getattr(msg.channel, "id", 0), int(rules.repeat_window_sec))
        if cnt >= 2 or chs >= 2:
            tier = "STRICT"; strict_due_to = f"repeat({cnt})/cross({chs})"

    # 3-d) 아바타 pHash 온디맨드 (키워드 히트 & 닉 미적용일 때만)
    if not tier:
        try:
            from ..detectors.avatar import phash_on_demand  # lazy import
        except Exception:
            async def phash_on_demand(*args, **kwargs): return False  # fallback
        try:
            matched = await phash_on_demand(member, cfg, state)
        except Exception as e:
            log.warning("pHash 온디맨드 실패: %s", e)
            matched = False
        if matched:
            tier = "STRICT"; strict_due_to = "avatar-phash"

    # 4) NORMAL (누적 60점 이상)
    if not tier and score >= int(rules.sensitivity.get("msg_threshold_normal", 60)):
        tier = "NORMAL"

    if not tier:
        # 최소 로그만 (원하면 스킵 가능)
        payload = LogPayload(
            guild_id=msg.guild.id,
            user_id=msg.author.id,
            mention=msg.author.mention,
            channel_mention=getattr(msg.channel, "mention", None),
            created_at_utc=msg.created_at or now_utc(),
            avatar_url_256=str(getattr(msg.author.display_avatar.with_size(256), "url", "")),
            tier=None,
            score=score,
            score_threshold=int(rules.sensitivity.get("msg_threshold_normal", 60)),
            reasons=reasons, hits=hits,
            preview=(msg.content or "").strip(),
            jump_url=getattr(msg, "jump_url", None),
            policy_effect="Log",
        )
        await emit(client, cfg, "MESSAGE", payload)
        return

    # 5) 제재 실행 → 로그
    effect = await apply_policy("MESSAGE", msg, tier, cfg, state)
    payload = LogPayload(
        guild_id=msg.guild.id,
        user_id=msg.author.id,
        mention=msg.author.mention,
        channel_mention=getattr(msg.channel, "mention", None),
        created_at_utc=msg.created_at or now_utc(),
        avatar_url_256=str(getattr(msg.author.display_avatar.with_size(256), "url", "")),
        tier=tier,
        score=score,
        score_threshold=int(rules.sensitivity.get("msg_threshold_normal", 60)),
        reasons=(reasons + ([strict_due_to] if strict_due_to else [])),
        hits=hits,
        preview=(msg.content or "").strip(),
        jump_url=getattr(msg, "jump_url", None),
        policy_effect=effect,
    )
    await emit(client, cfg, "MESSAGE", payload)
