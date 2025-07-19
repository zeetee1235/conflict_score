gpu가 딸려서 일단 본가 가서 마저 해야될듯

# Conflict Score

## 개발환경 세팅

1. Python 3.8 이상 설치
2. 의존성 설치
```bash
pip install -r requirements.txt
```
3. 환경 변수 설정
`.env` 파일을 `.env.example` 참고하여 작성

## 실행 방법
```bash
python src/main.py
```

## 주요 파일 설명
- src/main.py: 메인 실행 파일
- src/bot.py: 봇 로직
- src/config.py: 환경설정
- src/database_manager.py: DB 관리
- src/dc_api_manager.py: DC API 연동
- src/gpt_api_manager.py: GPT 연동
- src/utils.py: 유틸리티 함수

## 문의
이슈는 Github Issue로 남겨주세요.

## 설정

### 환경 변수

Google API 키를 환경 변수로 설정하세요:

```sh
export GOOGLE_API_KEY=your_google_api_key
```

### 설정 파일

config.py에서 봇 설정을 구성하세요:

```python
import os
import google.generativeai as genai

# 설정 상수
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')  # API 키를 환경 변수로 설정
BOARD_ID = 'your_board_id'  # 갤러리 ID
USERNAME = 'your_username'  # 사용자명
PASSWORD = 'your_password'  # 비밀번호
PERSONA = """
I am the "Official #1 Fan of Kim Hoya" who fervently likes Kim Hoya.
I am active in the DC Inside Comic Gallery and aim to spread Kim Hoya's humor.
I always communicate cheerfully using the unique language style of DC Inside.
I do not use symbols, and all writings are in Korean.
"""
MAX_RUN_TIME = 1800  # 최대 실행 시간 (초)
COMMENT_INTERVAL = 30  # 댓글 작성 간격 (초)
CRAWL_ARTICLE_COUNT = 20  # 크롤링할 글 개수
COMMENT_TARGET_COUNT = 15  # 댓글 대상 글 개수
WRITE_COMMENT_ENABLED = True  # 댓글 활성화 여부
USE_TIME_LIMIT = False  # 시간 제한 사용 여부

# Google API 설정
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name='gemini-1.5-flash')
generation_config = genai.GenerationConfig(
    temperature=0.6,
    top_k=1,
    max_output_tokens=750
)
```

### 설치

필요한 패키지를 설치하세요:

```sh
pip install -r requirements.txt -q
```

## 봇 실행

아래 명령어로 봇을 실행하세요:

```sh
python main.py
```