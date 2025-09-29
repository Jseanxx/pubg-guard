## PUBG Guard - systemd 서비스 배포 가이드

이 문서는 `python3 -m guard`로 실행하는 PUBG Guard를 systemd 서비스로 등록하는 방법을 설명합니다.

### 전제
- 서버 사용자: `wnstj111112`
- 프로젝트 경로: `/home/wnstj111112/pubg-guard`
- 진입 명령: `python3 -m guard`
- 환경변수 파일: `guard/env_pubg.sh`
- 파이썬 경로: `/usr/bin/python3` (필요 시 `which python3`로 확인)

### 1) 래퍼 스크립트 생성 (환경변수 로드 포함)
`/home/wnstj111112/run_pubg_guard_once.sh`

```bash
cat > /home/wnstj111112/run_pubg_guard_once.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd /home/wnstj111112/pubg-guard

# 환경변수 적용
if [ -f guard/env_pubg.sh ]; then
  set -a
  . guard/env_pubg.sh
  set +a
fi

exec /usr/bin/python3 -m guard
EOF

chmod +x /home/wnstj111112/run_pubg_guard_once.sh
```

### 2) systemd 유닛 파일 작성
`/etc/systemd/system/pubg-guard.service`

```bash
sudo bash -lc 'cat > /etc/systemd/system/pubg-guard.service << "EOF"\n[Unit]\nDescription=PUBG Guard Discord Bot\nAfter=network-online.target\n\n[Service]\nUser=wnstj111112\nWorkingDirectory=/home/wnstj111112/pubg-guard\nExecStart=/home/wnstj111112/run_pubg_guard_once.sh\nRestart=always\nRestartSec=5\nStandardOutput=journal\nStandardError=journal\n# 선택: 초기에는 비활성, 안정 후 점진 적용\n# MemoryMax=800M\n# 보안 하드닝(선택)\n# NoNewPrivileges=true\n# PrivateTmp=true\n# ProtectSystem=full\n# ProtectHome=true\n\n[Install]\nWantedBy=multi-user.target\nEOF'
```

### 3) 서비스 적용/기동/검증

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pubg-guard
sudo systemctl status pubg-guard | cat
journalctl -u pubg-guard -f
```

### 4) 운영 중 자주 쓰는 명령

```bash
# 제어
sudo systemctl restart pubg-guard
sudo systemctl stop pubg-guard
sudo systemctl start pubg-guard
sudo systemctl disable pubg-guard

# 로그
journalctl -u pubg-guard --since "1 hour ago" -o short-iso | cat
journalctl -u pubg-guard -f
```

### 5) tmux와의 관계
- 운영은 systemd로 구동하고, tmux는 디버깅용으로만 사용하세요.
- 같은 봇을 tmux와 systemd에서 동시에 실행하지 마세요(중복 인스턴스 금지).

### 6) 트러블슈팅
- 서비스가 바로 종료될 때: `journalctl -u pubg-guard -n 200 -o short-iso | cat`
- 환경변수 미적용 의심 시: 래퍼 스크립트에서 `env | sort | head -n 20`로 점검
- 메모리 이슈: 스왑(1~2G) 활성화, 불필요 intents/캐시 축소


