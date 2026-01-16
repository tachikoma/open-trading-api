# 텔레그램 알림 설정 가이드

짧게: 텔레그램 알림을 사용하려면 `BotFather`로 봇을 만들고 `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID`를 `.env`에 설정한 뒤 `TELEGRAM_ENABLED=1`로 활성화한 뒤 봇을 재시작하세요.

1) 봇 생성 및 토큰 얻기
- 텔레그램에서 `@BotFather`를 열고 `/newbot` 명령으로 새 봇을 생성합니다.
- BotFather가 발급하는 `Bot Token`(형태: `123456:ABC...`)을 복사하세요.

2) 채팅 ID 확인
- 개인 채팅 ID 확인(간단): 브라우저에서 `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` 호출 후 메시지를 보내고 응답에 있는 `chat.id` 확인
- 또는 편리한 방법: `@userinfobot` 또는 `@RawDataBot` 등으로 자신의 chat id 조회
- 그룹에 봇을 추가하면 그룹 chat id는 음수(`-123456789`)입니다.

3) `.env`에 설정 (프로젝트 루트)
```text
# .env (절대값 또는 프로젝트 루트/.env)
TELEGRAM_ENABLED=1
TELEGRAM_BOT_TOKEN="123456:ABCDefGhI_jklMNopQRs"
TELEGRAM_CHAT_ID="-123456789"
TELEGRAM_TIMEOUT_SEC=3
```

주의: 절대 실 계정의 민감 정보(계좌번호, 시크릿 등)를 함께 저장하거나 커밋하지 마세요. `.env`는 로컬에만 보관하고 `.gitignore`에 추가되어야 합니다.

4) 테스트 전송 (curl 사용)
- 환경변수로 설정한 뒤 아래 curl로 빠르게 확인할 수 있습니다:

```bash
export TELEGRAM_ENABLED=1
export TELEGRAM_BOT_TOKEN="<YOUR_TOKEN>"
export TELEGRAM_CHAT_ID="<YOUR_CHAT_ID>"
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id=${TELEGRAM_CHAT_ID} -d text="Test message from trading bot"
```

5) 프로젝트에서 활성화
- `.env`에 값을 넣고 `uv run`으로 봇을 재시작하면 `Config`가 `.env`값을 읽습니다.
- 예: 프로젝트 루트에서

```bash
uv run trading_bot/run_bot.py
```

6) 안전 및 운영 팁
- 텔레그램 메시지 폭주 주의: 테스트 시 많은 자동 메시지를 보내지 마세요. 실전에서는 주문/오류 등 핵심 이벤트만 전송 권장.
- 토큰은 절대 공개 저장소에 커밋하지 마세요.
- Group chat id는 음수일 수 있으니 `.env`에 그대로 입력하세요.

문제 발생 시 저에게 알려주시면 테스트 스크립트(간단한 `telegram_test.py`)를 만들어 드리겠습니다.
