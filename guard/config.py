# guard/config.py
from dataclasses import dataclass
import os
from pathlib import Path

def _parse_id_list(s: str) -> list[int]:
    out = []
    for x in (s or "").split(","):
        x = x.strip()
        if x.isdigit():
            out.append(int(x))
    return out

@dataclass(frozen=True)
class Config:
    # Discord
    token: str
    guild_id: int

    # Window / thresholds
    window_days: int
    timeout_hours: int

    # Channels (monitor scopes)
    channel_qr_monitor_ids: list[int]       # 이미지 QR 상시 스캔 채널들(미디어/포럼)
    channel_msg_monitor_ids: list[int]      # 텍스트 정밀감시 채널들(구직1~4, 도움요청 등)
    msg_exempt_log_only_ids: list[int]      # 텍스트 로그만(제재❌) 채널(예: 프리채팅)

    # Log channels
    log_qr_channel_id: int
    log_phish_channel_id: int
    log_sub_channel_ids: list[int]

    # Policies / switches
    ban_on_qr: bool
    ban_on_strict: bool
    ban_on_normal: bool

    policy_qr: str          # log|delete|timeout|delete_timeout
    policy_message: str
    policy_avatar: str

    # pHash / refs
    phish_dir: str
    phash_threshold: int
    phash_cooldown_h: int
    phash_sem: int

    # QR
    qr_max_bytes: int
    qr_sem: int
    qr_exclude_gif: bool

    # Rules
    rules_path: str
    debug: bool

def load_config() -> Config:
    HERE = Path(__file__).resolve().parent  # ✅ config.py 기준 절대경로

    return Config(
        token=os.getenv("DISCORD_TOKEN", ""),
        guild_id=int(os.getenv("GUILD_ID", "0")),

        window_days=int(os.getenv("WINDOW_DAYS", "50")),
        timeout_hours=int(os.getenv("TIMEOUT_HOURS", "24")),

        channel_qr_monitor_ids=_parse_id_list(os.getenv("CHANNEL_QR_MONITOR_IDS", "")),
        channel_msg_monitor_ids=_parse_id_list(os.getenv("CHANNEL_MSG_MONITOR_IDS", "")),
        msg_exempt_log_only_ids=_parse_id_list(os.getenv("MSG_EXEMPT_LOG_ONLY_IDS", "")),

        log_qr_channel_id=int(os.getenv("LOG_QR_CHANNEL_ID", "0")),
        log_phish_channel_id=int(os.getenv("LOG_PHISH_CHANNEL_ID", "0")),
        log_sub_channel_ids=_parse_id_list(os.getenv("LOG_SUB_CHANNEL_IDS", "")),

        ban_on_qr=os.getenv("BAN_ON_QR", "1") in {"1","true","True"},
        ban_on_strict=os.getenv("BAN_ON_STRICT", "1") in {"1","true","True"},
        ban_on_normal=os.getenv("BAN_ON_NORMAL", "0") in {"1","true","True"},

        policy_qr=os.getenv("POLICY_QR", "delete_timeout").lower(),
        policy_message=os.getenv("POLICY_MESSAGE", "delete_timeout").lower(),
        policy_avatar=os.getenv("POLICY_AVATAR", "log").lower(),

        phish_dir=os.getenv("PHISH_DIR", str(HERE / "phish_avatars")),
        phash_threshold=int(os.getenv("PHASH_THRESHOLD", "8")),
        phash_cooldown_h=int(os.getenv("PHASH_COOLDOWN_H", "6")),
        phash_sem=int(os.getenv("PHASH_SEM", "3")),

        qr_max_bytes=int(os.getenv("QR_MAX_BYTES", str(5 * 1024 * 1024))),
        qr_sem=int(os.getenv("QR_SEM", "2")),
        qr_exclude_gif=os.getenv("QR_EXCLUDE_GIF", "1") in {"1","true","True"},

        rules_path=os.getenv("RULES_PATH", str(HERE / "rules.json")),
        debug=os.getenv("DEBUG", "0") in {"1","true","True"},
    )