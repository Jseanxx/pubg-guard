# guard/emit.py
import logging
from datetime import datetime, timezone, timedelta
from typing import Iterable

import discord
from .types import EventKind, LogPayload
from .config import Config

log = logging.getLogger("guard.emit")
UTC = timezone.utc
KST = timezone(timedelta(hours=9))

def now_utc() -> datetime: return datetime.now(UTC)
def fmt_kst(dt: datetime | None) -> str:
    if not dt: return "N/A"
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")

BLANK = "\u200b"
ALLOW_NONE = discord.AllowedMentions.none()

def _build_qr_text(p: LogPayload) -> str:
    return "\n".join([
        "[QR코드 이미지 삭제]",
        f"대상: {p.mention}",
        f"시간: {fmt_kst(p.created_at_utc)}",
        f"링크: {p.qr_text_obfuscated or '-'}",
        f"제재: {p.policy_effect or 'None'}",
    ])

def _pad3(emb: discord.Embed, n: int):
    for _ in range(n):
        emb.add_field(name=BLANK, value=BLANK, inline=True)

def _build_avatar_embed(p: LogPayload) -> discord.Embed:
    emb = discord.Embed(title="[프로필 사진 탐지]", color=discord.Color.green(), timestamp=now_utc())
    if p.avatar_url_256:
        try: emb.set_thumbnail(url=p.avatar_url_256)
        except Exception: pass
    emb.description = p.mention
    emb.add_field(name="시간", value=fmt_kst(p.created_at_utc), inline=True)
    emb.add_field(name="입장", value=fmt_kst(p.joined_at_utc), inline=True)
    emb.add_field(name="ID", value=str(p.user_id), inline=True)
    emb.add_field(name="모니터링", value="-", inline=True)  # 필요 시 외부에서 대체
    det = ", ".join(p.hits or p.reasons or []) or "-"
    emb.add_field(name="탐지", value=det, inline=True)
    _pad3(emb, 1)
    return emb

def _build_message_embed(p: LogPayload) -> discord.Embed:
    emb = discord.Embed(title="[피싱 메시지 의심]", color=discord.Color.from_str("#DC2626"), timestamp=now_utc())
    if p.avatar_url_256:
        try: emb.set_thumbnail(url=p.avatar_url_256)
        except Exception: pass
    emb.description = p.mention
    emb.add_field(name="시간", value=fmt_kst(p.created_at_utc), inline=True)
    emb.add_field(name="채널", value=(p.channel_mention or "-"), inline=True)
    emb.add_field(name="ID", value=str(p.user_id), inline=True)
    tier = p.tier or "-"
    score_str = "-"
    if p.tier == "NORMAL":
        score_str = f"{p.score or 0}/{p.score_threshold or 60}"
    elif p.tier == "STRICT":
        score_str = f"{p.score or 0}/—"
    emb.add_field(name="티어", value=tier, inline=True)
    emb.add_field(name="점수", value=score_str, inline=True)
    emb.add_field(name="제재", value=(p.policy_effect or "None"), inline=True)
    det = ", ".join(p.hits or (p.reasons or [])) or "-"
    emb.add_field(name="탐지", value=det, inline=False)
    if p.preview is not None:
        preview = p.preview if len(p.preview) <= 600 else (p.preview[:597] + "...")
        emb.add_field(name="메시지", value=(preview or "(첨부만 있음)"), inline=False)
    if p.jump_url:
        emb.url = p.jump_url
    return emb

async def emit(client: discord.Client, cfg: Config, kind: EventKind, payload: LogPayload):
    # 대상 채널 결합
    mains = [cfg.log_qr_channel_id] if kind == "QR" else [cfg.log_phish_channel_id]
    targets: list[int] = []
    for cid in list({*mains, *cfg.log_sub_channel_ids}):
        if cid: targets.append(cid)
    if not targets: return

    if kind == "QR":
        text = _build_qr_text(payload)
        for cid in targets:
            ch = client.get_channel(cid) or await client.fetch_channel(cid)
            try: await ch.send(text, allowed_mentions=ALLOW_NONE)
            except Exception as e: log.warning("QR 로그 전송 실패(%s): %s", cid, e)
        return

    emb = _build_avatar_embed(payload) if kind == "AVATAR" else _build_message_embed(payload)
    for cid in targets:
        ch = client.get_channel(cid) or await client.fetch_channel(cid)
        try: await ch.send(embed=emb, allowed_mentions=ALLOW_NONE)
        except Exception as e: log.warning("%s 로그 전송 실패(%s): %s", kind, cid, e)
