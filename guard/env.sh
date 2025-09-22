# --- 필수 ---
export DISCORD_TOKEN="..."               # 봇 토큰
export GUILD_ID="123456789012345678"     # 길드 ID

# --- 감시 스코프(쉼표로 구분된 채널 ID 리스트) ---
# 이미지 QR 상시 스캔 채널(미디어, 포럼 parent 채널 ID)
export CHANNEL_QR_MONITOR_IDS="111,222"
# 텍스트 정밀 감시 채널(구인구직1~4, 도움요청 parent 채널 ID)
export CHANNEL_MSG_MONITOR_IDS="333,444,555,666,777"
# 텍스트는 로그만(제재❌) 채널(프리채팅 등)
export MSG_EXEMPT_LOG_ONLY_IDS="888"

# --- 로그 채널 ---
export LOG_QR_CHANNEL_ID="1095142986939109436"     # QR 메인
export LOG_PHISH_CHANNEL_ID="1414799160837931028"  # 메시지/아바타 메인
export LOG_SUB_CHANNEL_IDS="1416449915311231237"   # 서브(선택)

# --- 윈도/정책/스위치 ---
export WINDOW_DAYS="50"                 # 텍스트 정밀 감시: 조인 ≤ N일
export TIMEOUT_HOURS="24"

# 정책: log | delete | timeout | delete_timeout
export POLICY_QR="delete_timeout"       # QR 정책(권장: delete_timeout 또는 delete)
export POLICY_MESSAGE="delete_timeout"  # 텍스트 정책
export POLICY_AVATAR="log"

# 즉시 Ban 스위치
export BAN_ON_QR="1"                    # ✅ QR 검출 → Ban
export BAN_ON_STRICT="1"                # ✅ STRICT → Ban
export BAN_ON_NORMAL="0"                # 필요 시 켜기

# --- pHash / QR ---
export PHISH_DIR="./phish_avatars"
export PHASH_THRESHOLD="8"              # 6~8 추천
export PHASH_COOLDOWN_H="6"             # 온디맨드 검사 쿨다운
export PHASH_SEM="3"                    # 동시성
export QR_MAX_BYTES="5242880"           # 5MB
export QR_SEM="2"
export QR_EXCLUDE_GIF="1"

# --- 기타 ---
export RULES_PATH="./rules.json"
export DEBUG="0"
