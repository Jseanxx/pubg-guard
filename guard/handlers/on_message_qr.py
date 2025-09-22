# guard/handlers/on_message_qr.py
import logging
from datetime import datetime, timezone, timedelta

import discord

from ..config import Config
from ..rules import Rules
from ..state import State
from ..schemas import LogPayload
from ..emit import emit
from ..policy import apply_policy
from ..detectors.qr import is_scannable_attachment, detect_qr_bytes, obfuscate

log = logging.getLogger("guard.handlers.on_message_qr")
UTC = timezone.utc
def now_utc(): return datetime.now(UTC)

def _channel_in_list(msg: discord.Message, ids: list[int]) -> bool:
    if not ids: return False
    ch = msg.channel
    if getattr(ch, "id", None) in ids: return True
    parent_id = getattr(getattr(ch, "parent", None), "id", None)
    return parent_id in ids

async def handle_message_qr(
    client: discord.Client, cfg: Config, rules: Rules, state: State, msg: discord.Message
):
    if not getattr(msg, "guild", None): return
    if not msg.attachments: return
    if not _channel_in_list(msg, cfg.channel_qr_monitor_ids): return

    for att in msg.attachments:
        if not is_scannable_attachment(att, cfg):
            continue
        if state.caches.att_ttl.contains(att.id):
            continue
        state.caches.att_ttl.add(att.id)

        try:
            async with state.conc.qr_sem:
                data = await att.read()
        except Exception:
            continue
        if not data:
            continue

        texts = await detect_qr_bytes(data)
        if not texts:
            continue

        # 조인≤WINDOW_DAYS 일자 가드: 윈도우 밖이면 제재 스킵하고 로그만
        member = msg.author if isinstance(msg.author, discord.Member) else None
        if (not member) and msg.guild:
            try:
                member = msg.guild.get_member(msg.author.id) or await msg.guild.fetch_member(msg.author.id)
            except Exception:
                member = None

        do_enforce = False
        try:
            if member and getattr(member, "joined_at", None):
                do_enforce = (now_utc() - member.joined_at) <= timedelta(days=cfg.window_days)
        except Exception:
            do_enforce = False

        if do_enforce:
            effect = await apply_policy("QR", msg, tier=None, cfg=cfg, state=state)
        else:
            effect = "Log (old-member)"

        payload = LogPayload(
            guild_id=msg.guild.id,
            user_id=msg.author.id,
            mention=msg.author.mention,
            channel_mention=getattr(msg.channel, "mention", None),
            created_at_utc=msg.created_at or now_utc(),
            qr_text_obfuscated=obfuscate(texts[0]),
            policy_effect=effect,
        )
        await emit(client, cfg, "QR", payload)
        return  # 한 번만 로그/제재
