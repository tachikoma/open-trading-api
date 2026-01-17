#!/usr/bin/env bash
set -euo pipefail

# kis 전용 재시작 스크립트
# 사용법: ~/restart-kis.sh [-n NAME] [-w WORKDIR] [-c CMD_STR]

# 기본값
NAME="kis"
WORKDIR="$HOME/investment/open-trading-api/trading_bot"
CMD_STR="uv run run_bot.py"

usage() {
  cat <<EOF
Usage:
  $0 [-n NAME] [-w WORKDIR] [-c CMD_STR]
EOF
  exit 1
}

# 파라미터 파싱
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--name) NAME="$2"; shift 2 ;;
    -w|--workdir) WORKDIR="$2"; shift 2 ;;
    -c|--cmd) CMD_STR="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "알 수 없는 옵션: $1" >&2; usage ;;
  esac
done

PID_FILE="$HOME/.${NAME}.pid"
LOG_DIR="${WORKDIR}/logs"

mkdir -p "$LOG_DIR"

# expand ~ in WORKDIR
WORKDIR="${WORKDIR/#\~/$HOME}"

# 공통 스크립트 로드 및 실행
source "$(dirname "$0")/restart-common.sh"
