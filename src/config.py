import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수에서 API 키를 불러오고, 쉼표로 구분된 값을 리스트로 변환
API_KEYS = os.getenv('API_KEYS').split(',') if os.getenv('API_KEYS') else None

# 모델 설정: 기본 로컬 Llama 모델로 설정
MODEL_NAME = os.getenv('MODEL_NAME', 'Bllossom/llama-3.2-Korean-Bllossom-3B')
# Handle inline comments in environment variables
_gen_temp_raw = os.getenv('GEN_TEMPERATURE', '0.7')
_gen_temp_clean = _gen_temp_raw.split('#')[0].strip()
GEN_TEMPERATURE = float(_gen_temp_clean)
# Max tokens for generation
_max_output_raw = os.getenv('GEN_MAX_OUTPUT_TOKENS', '300')
_max_output_clean = _max_output_raw.split('#')[0].strip()
GEN_MAX_OUTPUT_TOKENS = int(_max_output_clean)

# Generation Config
GENERATION_CONFIG = {
    "temperature": GEN_TEMPERATURE,
    "max_tokens": GEN_MAX_OUTPUT_TOKENS,
    # 'top_p'와 'frequency_penalty' 등 다른 설정을 추가로 정의할 수 있음
}

# Helper to load and clean environment variables (strips inline comments)
def _get_env(key: str, default: str = None) -> str:
    raw = os.getenv(key, default)
    return raw.split('#')[0].strip() if raw is not None else raw

# 기본 봇 설정 (공통 설정)
DEFAULT_BOT_SETTINGS = {
    'max_run_time': int(_get_env('BOT_MAX_RUN_TIME', '1800')),
    'article_interval': int(_get_env('BOT_ARTICLE_INTERVAL', '90')),
    'comment_interval': int(_get_env('BOT_COMMENT_INTERVAL', '45')),
    'crawl_article_count': int(_get_env('BOT_CRAWL_ARTICLE_COUNT', '20')),
    'comment_target_count': int(_get_env('BOT_COMMENT_TARGET_COUNT', '20')),
    'write_article_enabled': _get_env('BOT_WRITE_ARTICLE_ENABLED', 'True') == 'True',
    'write_comment_enabled': _get_env('BOT_WRITE_COMMENT_ENABLED', 'True') == 'True',
    'record_memory_enabled': _get_env('BOT_RECORD_MEMORY_ENABLED', 'True') == 'True',
    'record_data_enabled': _get_env('BOT_RECORD_DATA_ENABLED', 'True') == 'True',
    'use_time_limit': _get_env('BOT_USE_TIME_LIMIT', 'False') == 'True',
    'load_memory_enabled': _get_env('BOT_LOAD_MEMORY_ENABLED', 'True') == 'True',
    'load_data_enabled': _get_env('BOT_LOAD_DATA_ENABLED', 'True') == 'True',
    'gallery_record_interval': int(_get_env('BOT_GALLERY_RECORD_INTERVAL', '600')),
    'username': _get_env('BOT_USERNAME'),
    'password': _get_env('BOT_PASSWORD'),
    'persona': _get_env('BOT_PERSONA')
}
