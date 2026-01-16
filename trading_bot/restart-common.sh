#!/usr/bin/env bash
set -euo pipefail

# 공통 재시작 스크립트 함수들
# 이 파일은 각 전용 스크립트에서 source하여 사용

# 전역 변수: NAME, WORKDIR, CMD_STR, PID_FILE, LOG_DIR, LOG_FILE
# 각 스크립트에서 설정 후 source

stop_existing() {
  if [[ -f "$PID_FILE" ]]; then
    PID=$(<"$PID_FILE")
    if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null; then
      printf "기존 프로세스(%s) 종료 중...\n" "$PID"
      kill "$PID" 2>/dev/null || true
      for i in {1..10}; do
        if kill -0 "$PID" 2>/dev/null; then sleep 1; else break; fi
      done
      if kill -0 "$PID" 2>/dev/null; then
        printf "강제 종료 %s\n" "$PID"
        kill -9 "$PID" 2>/dev/null || true
      fi
    fi
    rm -f "$PID_FILE"
    return
  fi

  # PID 파일 없음 -> WORKDIR 및 CMD 기반으로 프로세스 검색 및 종료
  local pattern
  pattern=$(echo "$CMD_STR" | awk '{print $NF}')
  if [[ -n "$pattern" ]]; then
    PIDS=$(pgrep -f "${WORKDIR}.*${pattern}" || true)
    if [[ -n "$PIDS" ]]; then
      for p in $PIDS; do
        if [[ "$p" =~ ^[0-9]+$ ]] && kill -0 "$p" 2>/dev/null; then
          printf "발견된 프로세스 종료: %s\n" "$p"
          kill "$p" 2>/dev/null || true
          sleep 1
          if kill -0 "$p" 2>/dev/null; then kill -9 "$p" 2>/dev/null || true; fi
        fi
      done
    fi
  fi
}

start_new() {
  printf "작업디렉토리: %s\n명령: %s\n로그: %s\n" "$WORKDIR" "$CMD_STR" "$LOG_FILE"
  cd "$WORKDIR" || { echo "WORKDIR 없음: $WORKDIR" >&2; exit 1; }

  # nohup으로 실행
  nohup bash -lc "$CMD_STR" >> "$LOG_FILE" 2>&1 &
  NEW_PID=$!
  echo "$NEW_PID" > "$PID_FILE"
  disown "$NEW_PID" 2>/dev/null || true
  printf "시작됨: PID=%s, PID파일=%s\n" "$NEW_PID" "$PID_FILE"
}

# 메인 로직 실행
stop_existing
start_new
