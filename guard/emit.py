# guard/emit.py
import logging
from datetime import datetime, timezone, timedelta
from typing import Iterable, Optional

import discord
from .schemas import EventKind, LogPayload
from .config import Config

log = logging.getLogger("guard.emit")
UTC = timezone.utc
KST = timezone(timedelta(hours=9))
RED = discord.Color.from_str("#DC2626")
GREY = discord.Color.from_str("#3b3b41")

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

def _build_avatar_embed(p: LogPayload, color: Optional[discord.Color] = None) -> discord.Embed:
    emb = discord.Embed(title="[프로필 사진 탐지]", timestamp=now_utc())
    if color is not None:
        emb.color = color
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

def _build_message_embed(p: LogPayload, color: Optional[discord.Color] = None) -> discord.Embed:
    emb = discord.Embed(title="[피싱 메시지 의심]", timestamp=now_utc())
    if color is not None:
        emb.color = color
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

class _BanView(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, custom_id="guard:ban")
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        client: discord.Client = interaction.client
        guild = interaction.guild or (client.get_guild(interaction.guild_id) if interaction.guild_id else None)
        if not guild:
            return await interaction.followup.send("길드 조회 실패", ephemeral=True)

        # 권한 체크: ban_members 또는 환경변수 롤
        member = guild.get_member(interaction.user.id) or await guild.fetch_member(interaction.user.id)
        if not member:
            return await interaction.followup.send("멤버 조회 실패", ephemeral=True)
        can_ban = getattr(member.guild_permissions, "ban_members", False)
        cfg = getattr(client, "_guard_cfg", None)
        if cfg and (cfg.ban_button_role_ids and not can_ban):
            can_ban = any(r.id in set(cfg.ban_button_role_ids) for r in (member.roles or []))
        if not can_ban:
            return await interaction.followup.send("권한 없음", ephemeral=True)

        # 대상 사용자 ID를 임베드에서 추출(ID 필드 또는 설명 mention에서 파싱)
        target_user_id: Optional[int] = None
        try:
            emb = (interaction.message.embeds or [None])[0]
            if emb:
                # ID 필드 찾기
                for f in (emb.fields or []):
                    if (f.name or "").strip().upper() == "ID":
                        s = (f.value or "").strip()
                        if s.isdigit():
                            target_user_id = int(s)
                            break
        except Exception:
            target_user_id = None
        if not target_user_id:
            return await interaction.followup.send("대상 ID 파싱 실패", ephemeral=True)

        # 중복 방지 (best-effort): (guild_id, user_id, message_id)
        st = getattr(client, "_guard_state", None)
        if st:
            key = (guild.id, target_user_id, interaction.message.id)
            exp = st.caches.ban_action_exp.get(key, 0)
            now = now_utc().timestamp()
            if exp and exp > now:
                return await interaction.followup.send("이미 처리 중이거나 완료됨", ephemeral=True)
            st.caches.ban_action_exp[key] = now + 300

        # Ban 시도 (유저가 나갔어도 ID ban 가능)
        try:
            target = guild.get_member(target_user_id) or discord.Object(id=target_user_id)
            await guild.ban(target, reason=f"Manual ban via button by {interaction.user}")
        except Exception as e:
            return await interaction.followup.send(f"밴 실패: {e}", ephemeral=True)

        # 버튼 비활성화 + 임베드 색상 무색으로 변경
        try:
            # 임베드 색상 제거(기본값)
            emb = None
            if interaction.message.embeds:
                emb = interaction.message.embeds[0]
                try:
                    emb.color = GREY
                except Exception:
                    pass
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
                    item.label = f"Banned by {member.display_name}"
            if emb is not None:
                try:
                    # 무지정(기본)로 되돌리기
                    emb.color = GREY
                except Exception:
                    pass
                await interaction.message.edit(embed=emb, view=self)
            else:
                await interaction.message.edit(view=self)
        except Exception:
            pass
        # 성공 시 별도 완료 메시지 전송하지 않음(임베드 라벨로 피드백)
        return

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

    # 색상 결정: 버튼이 있는 MESSAGE는 빨강, 그 외는 기본(무지정)
    lower_effect = (payload.policy_effect or "").lower()
    show_button = (
        kind == "MESSAGE"
        and cfg.enable_ban_button
        and ("timeout" in lower_effect)
    )
    color = (RED if show_button else None)
    emb = _build_avatar_embed(payload, color=color) if kind == "AVATAR" else _build_message_embed(payload, color=color)
    for cid in targets:
        ch = client.get_channel(cid) or await client.fetch_channel(cid)
        try:
            view = _BanView(timeout=None) if show_button else None
            await ch.send(embed=emb, allowed_mentions=ALLOW_NONE, view=view)
        except Exception as e: log.warning("%s 로그 전송 실패(%s): %s", kind, cid, e)
