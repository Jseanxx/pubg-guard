# --- 필수 ---
export DISCORD_TOKEN=""               # 봇 토큰
export GUILD_ID="589033421121126400"     # 길드 ID

# --- 감시 스코프(쉼표로 구분된 채널 ID 리스트) ---
# 이미지 QR 상시 스캔 채널(미디어, 포럼 parent 채널 ID)
export CHANNEL_QR_MONITOR_IDS="1091322105943044206,1049395963942420600"
# 텍스트 정밀 감시 채널(구인구직1~4, 도움요청 parent 채널 ID)
export CHANNEL_MSG_MONITOR_IDS="1049396238996475905,1049396275717603470,1049396305459417178,1049396498124775504,1049395963942420600,1091322105943044206,929985944612921416,944213652607762432,590767390908743680,1420630317148016680"
# 면책 적용 채널(프리채팅 등): 키워드 근처에 부정/경고 표현 있으면 로그만 처리
export MSG_EXEMPT_LOG_ONLY_IDS="590767390908743680"

# --- 로그 채널 ---
export LOG_QR_CHANNEL_ID="1095142986939109436"     # QR 메인
export LOG_PHISH_CHANNEL_ID="1414799160837931028"  # 메시지/아바타 메인
export LOG_SUB_CHANNEL_IDS="1416449915311231237"   # 서브(선택): 메인 로그와 동일 알림을 서브 채널에도 동시 전송

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
export PHASH_THRESHOLD="8"              # 6~8 추천
export PHASH_COOLDOWN_H="6"             # 온디맨드 검사 쿨다운
export PHASH_SEM="3"                    # 동시성
export QR_MAX_BYTES="5242880"           # 5MB
export QR_SEM="2"
export QR_EXCLUDE_GIF="1"

# --- 기타 ---
export DEBUG="0"
export ENABLE_BAN_BUTTON="1"
# 선택: 버튼 클릭 허용 롤(없으면 ban_members 권한 필요)
export BAN_BUTTON_ROLE_IDS=""
