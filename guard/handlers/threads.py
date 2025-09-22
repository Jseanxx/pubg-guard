# guard/handlers/threads.py
import logging, asyncio
from typing import Optional
from datetime import datetime, timezone, timedelta

import discord

from ..schemas import LogPayload
from ..config import Config
from ..rules import Rules
from ..state import State
from ..emit import emit
from ..policy import apply_policy
from ..detectors.message import score_message, profile_visit_in_reasons, negation_guard
from ..detectors.qr import is_scannable_attachment, detect_qr_bytes, obfuscate

log = logging.getLogger("guard.handlers.threads")
UTC = timezone.utc
def now_utc(): return datetime.now(UTC)

def _channel_in_list(obj, ids: list[int]) -> bool:
    if not ids: return False
    # thread.parent(포럼), 또는 채널 그 자체
    cid = None
    if isinstance(obj, discord.Thread):
        cid = getattr(getattr(obj, "parent", None), "id", None)
    else:
        cid = getattr(obj, "id", None)
    return cid in ids

def _joined_within_days(m: Optional[discord.Member], days: int) -> bool:
    if not m or not getattr(m, "joined_at", None):
        return False
    return (now_utc() - m.joined_at) <= timedelta(days=days)

async def _resolve_owner(thread: discord.Thread) -> Optional[discord.Member]:
    g = getattr(thread, "guild", None)
    if not g: return None
    oid = getattr(thread, "owner_id", None)
    if not oid: return None
    m = g.get_member(oid)
    if m: return m
    try:
        return await g.fetch_member(oid)
    except Exception:
        return None

async def handle_thread_create(
    client: discord.Client, cfg: Config, rules: Rules, state: State, thread: discord.Thread
):
    # 포럼 텍스트 모니터링: parent가 텍스트 감시 리스트에 있어야 함
    if not _channel_in_list(thread, cfg.channel_msg_monitor_ids):
        # 그래도 QR 스캔은 이미지 리스트에 있으면 수행(아래에서 스타터 메시지 처리)
        pass

    # 1) 제목 평가 (면책 가드 포함, 조인≤window)
    owner = await _resolve_owner(thread)
    if not owner:
        return
    if not _joined_within_days(owner, cfg.window_days):
        # 신입 아님 → 텍스트 제재 루틴 스킵
        pass
    else:
        title = (thread.name or "").strip()
        score, reasons, hits, _ = score_message(title, rules)
        if (reasons or hits):
            # 면책(부정·경고 근접) → 로그만
            if negation_guard(title, hits or reasons, rules, window=20):
                payload = LogPayload(
                    guild_id=thread.guild.id, user_id=owner.id, mention=owner.mention,
                    channel_mention=getattr(thread.parent, "mention", None),
                    created_at_utc=now_utc(), avatar_url_256=str(getattr(owner.display_avatar.with_size(256), "url", "")),
                    tier=None, score=score, score_threshold=int(rules.sensitivity.get("msg_threshold_normal", 60)),
                    reasons=reasons, hits=hits, preview=f"[제목] {title}", jump_url=None,
                    policy_effect="Log (negation-guard)"
                )
                await emit(client, cfg, "MESSAGE", payload)
            else:
                # STRICT 여부
                tier = None
                strict_due = None
                # profile_visit 조합으로 STRICT 승격 제거 (점수 기반만)
                if score >= int(rules.sensitivity.get("msg_threshold_normal", 60)):
                    tier = "NORMAL"

                if tier:
                    # 스타터 메시지 가져와서 메시지 정책 재사용
                    starter_msg = None
                    try:
                        starter_msg = await thread.fetch_message(thread.id)
                    except Exception:
                        # 일부 케이스는 thread.last_message_id를 사용
                        if thread.last_message_id:
                            try:
                                starter_msg = await thread.fetch_message(thread.last_message_id)
                            except Exception:
                                starter_msg = None

                    if starter_msg and starter_msg.author and starter_msg.author.id == owner.id:
                        effect = await apply_policy("MESSAGE", starter_msg, tier, cfg, state)
                        payload = LogPayload(
                            guild_id=thread.guild.id, user_id=owner.id, mention=owner.mention,
                            channel_mention=getattr(thread.parent, "mention", None),
                            created_at_utc=now_utc(), avatar_url_256=str(getattr(owner.display_avatar.with_size(256), "url", "")),
                            tier=tier, score=score, score_threshold=int(rules.sensitivity.get("msg_threshold_normal", 60)),
                            reasons=reasons + ([strict_due] if strict_due else []), hits=hits,
                            preview=f"[제목] {title}", jump_url=None, policy_effect=effect
                        )
                        await emit(client, cfg, "MESSAGE", payload)

                        # 삭제 정책이면 스레드도 제거 시도 (중복 방지 위해 best-effort)
                        if cfg.policy_message in ("delete", "delete_timeout"):
                            try:
                                await thread.delete()
                            except Exception as e:
                                log.warning("스레드 삭제 실패: %s", e)
                    else:
                        # 메시지 객체가 없거나 남의 글이면 보수적으로 타임아웃만(정책 허용 시)
                        if cfg.policy_message in ("timeout", "delete_timeout"):
                            try:
                                until = now_utc() + timedelta(hours=cfg.timeout_hours)
                                await owner.edit(timed_out_until=until)
                            except Exception as e:
                                log.warning("타임아웃 실패(thread owner): %s", e)

    # 2) 스타터 메시지의 첨부 이미지에 대해 QR 상시 스캔 (이미지 모니터 리스트에 있을 때)
    if not _channel_in_list(thread, cfg.channel_qr_monitor_ids):
        return

    # 스타터 또는 첫 메시지 확보
    starter = None
    try:
        starter = await thread.fetch_message(thread.id)
    except Exception:
        if thread.last_message_id:
            try:
                starter = await thread.fetch_message(thread.last_message_id)
            except Exception:
                starter = None
    if not starter:
        return

    for att in starter.attachments or []:
        if not is_scannable_attachment(att, cfg):
            continue
        try:
            data = await att.read()
        except Exception:
            continue
        texts = await detect_qr_bytes(data)
        if not texts:
            continue

        # QR 정책 적용(즉시)
        effect = await apply_policy("QR", starter, tier=None, cfg=cfg, state=state)
        payload = LogPayload(
            guild_id=thread.guild.id, user_id=starter.author.id, mention=starter.author.mention,
            channel_mention=getattr(thread.parent, "mention", None),
            created_at_utc=starter.created_at or now_utc(),
            qr_text_obfuscated=obfuscate(texts[0]),
            policy_effect=effect,
        )
        await emit(client, cfg, "QR", payload)
        # 한 개라도 발견하면 종료(중복 로그 방지)
        return
