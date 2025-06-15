#!/bin/bash
# filepath: /home/dev/conflict_score/setting.sh
set -e  # 오류 발생 시 즉시 종료

# 파일 존재 여부 확인 함수
check_file() {
    if [ ! -f "$1" ]; then
        echo "Error: $1 not found. Exiting."
        exit 1
    fi
}

# 필요한 파일 확인
check_file "crawling.py"
check_file "main.py"

# Run crawling.py
python3 crawling.py
status=$?
if [ $status -eq 0 ]; then
    echo "Crawling completed successfully. Starting main.py..."
    python3 main.py
else
    echo "Crawling failed (exit code: $status). Exiting."
    exit $status
fi
