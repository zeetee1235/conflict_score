import logging
import re

def handle_exceptions(func):
    """
    비동기 함수에서 발생하는 예외를 처리합니다.
    
    :param func: 예외를 처리할 비동기 함수.
    :return: 예외를 처리한 비동기 래퍼 함수.
    """
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"{func.__name__} 함수에서 오류 발생: {e}", exc_info=True)
    return wrapper

def sanitize_text(text):
    """
    텍스트를 정리하여 원하지 않는 특수문자와 불필요한 공백을 제거합니다.
    
    :param text: 원본 텍스트.
    :return: 정리된 텍스트.
    """
    # 일반적인 구두점을 제외한 원하지 않는 특수문자와 " 제거
    sanitized_text = re.sub(r'[^\w\s.,!?\'()]', '', text)
    # 공백, 줄바꿈, 탭 등을 단일 공백으로 정리
    sanitized_text = re.sub(r'\s+', ' ', sanitized_text).strip()
    return sanitized_text

def clean_title(title):
    """
    제목에서 '제목'이라는 단어를 제거합니다.
    
    :param title: 원본 제목.
    :return: '제목'이라는 단어가 제거된 제목.
    """
    # "제목 "으로 시작하면 이를 제거
    if title.startswith("제목 "):
        title = title[len("제목 ") :]
    return title
