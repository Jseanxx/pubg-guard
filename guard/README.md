# PUBG Guard Bot

디스코드 피싱/QR 감시 봇.

## 준비

- Python 3.10+
- (권장) 가상환경

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
```

## 의존성 설치

- 한 번에 설치:
```bash
bash install_deps.sh
```

- 또는 수동:
```bash
python3 -m pip install -U pip wheel setuptools
python3 -m pip install -r requirements.txt
```

## 환경 변수

운영/테스트 중 하나를 선택해서 로드하세요.
```bash
source guard/env_pubg.sh   # 운영
# 또는
source guard/env_test.sh   # 테스트
```
필요 항목: `DISCORD_TOKEN`, `GUILD_ID`, `LOG_QR_CHANNEL_ID` 또는 `LOG_PHISH_CHANNEL_ID` 등.

## 실행

프로젝트 루트(아래에 `guard/` 폴더가 보이는 위치)에서:
```bash
python3 -m guard.app
```

## venv를 커밋하지 않는 이유

- 가상환경은 OS/파이썬 버전/경로에 종속적입니다.
- 대신 재현 가능한 설치를 위해 `requirements.txt`를 커밋합니다.
- 필요 시 다음으로 생성/설치하면 됩니다:
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## 개발 메모

- `types.py` → `schemas.py`로 파일명이 변경되었습니다. 모든 임포트는 `schemas`를 사용합니다.

