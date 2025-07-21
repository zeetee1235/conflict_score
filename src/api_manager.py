import logging
import random
import dc_api
from openai import AsyncOpenAI
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import asyncio

class DcApiManager:
    def __init__(self, board_id, username, password):
        """
        DcApiManager 클래스를 초기화합니다.

        :param board_id: 게시판 ID
        :param username: 사용자 이름
        :param password: 사용자 비밀번호
        """
        self.board_id = board_id
        self.username = username
        self.password = password
        self.api = dc_api.API()

    async def start(self):
        """
        인스턴스를 시작합니다.
        """
        # 필요 시 초기화 작업을 여기에 추가합니다.
        pass

    async def close(self):
        """
        API 세션을 명시적으로 종료합니다.
        """
        try:
            await self.api.close()
            logging.info("API 세션이 종료되었습니다.")
        except Exception as e:
            logging.error(f"API 세션 종료 실패: {e}")

    async def write_document(self, title, content, is_minor=False):
        """
        문서를 게시합니다.

        :param title: 문서 제목
        :param content: 문서 내용
        :param is_minor: 부가적인 설정 (기본값: False)
        :return: None
        """
        try:
            await self.api.write_document(
                board_id=self.board_id,
                title=title,
                contents=content,
                name=self.username,
                password=self.password,
                is_minor=is_minor
            )
            logging.info(f"문서 작성 성공 : {title}")
        except Exception as e:
            logging.error(f"문서 작성 실패 : {e}")

    async def write_comment(self, document_id, content):
        """
        문서에 댓글을 게시합니다.

        :param document_id: 문서 ID
        :param content: 댓글 내용
        :return: 댓글 ID 또는 None
        """
        try:
            comment_id = await self.api.write_comment(
                board_id=self.board_id,
                document_id=document_id,
                name=self.username,
                password=self.password,
                contents=content
            )
            logging.info(f"댓글 작성 성공 ({document_id}) : {content}")
            return comment_id
        except Exception as e:
            logging.error(f"댓글 작성 실패 : {e}")
            return None

    async def get_random_document_info(self):
        """
        무작위로 문서 정보를 가져옵니다.

        :return: (문서 ID, 문서 제목) 튜플 또는 None
        """
        try:
            articles = [article async for article in self.api.board(board_id=self.board_id, num=10)]
            if articles:
                random_article = random.choice(articles)
                return random_article.id, random_article.title
            else:
                logging.warning("게시물이 없습니다.")
                return None
        except Exception as e:
            logging.error(f"문서 정보 가져오기 실패 : {e}")
            return None


class GptApiManager:
    def __init__(self, api_key, model_name="gpt-4o", generation_config=None):
        """
        GptApiManager 클래스를 초기화합니다.

        :param api_key: OpenAI API 키
        :param model_name: 사용할 모델 이름 (기본값: "gpt-4")
        :param generation_config: 생성 설정 (선택적)
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model_name = model_name
        self.generation_config = generation_config or {}

    async def generate_content(self, prompt):
        """
        주어진 프롬프트를 사용하여 콘텐츠를 생성합니다.

        :param prompt: 콘텐츠 생성을 위한 프롬프트
        :return: 생성된 콘텐츠 문자열, 실패 시 None
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                **self.generation_config
            )

            content = response.choices[0].message.content.strip()
            return content
        except Exception as e:
            logging.error(f"콘텐츠 생성 실패: {e}")
            return None


class llamaManager:
    def __init__(self, api_key=None, model_name="Bllossom/llama-3.2-Korean-Bllossom-3B", generation_config=None):
        """
        GptApiManager 클래스를 초기화합니다. 로컬 Llama 모델을 사용합니다.

        :param api_key: 사용하지 않음
        :param model_name: 로컬 모델 이름
        :param generation_config: 생성 설정 (temperature, max_tokens 등)
        """
        self.model_name = model_name
        self.generation_config = generation_config or {}
        # 로컬 llama 모델 로드
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            device_map="auto"
        )
        self.model.config.pad_token_id = self.tokenizer.pad_token_id
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    async def generate_content(self, prompt: str) -> str:
        """
        로컬 Llama 모델을 사용하여 컨텐츠를 생성합니다.

        :param prompt: 컨텐츠 생성을 위한 프롬프트
        :return: 생성된 컨텐츠 문자열, 실패 시 빈 문자열
        """
        try:
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.generation_config.get('max_input_tokens', 2048)
            ).to(self.device)
            gen_kwargs = {
                'max_new_tokens': self.generation_config.get('max_tokens', 300),
                'temperature': self.generation_config.get('temperature', 0.7),
                'top_p': self.generation_config.get('top_p', 0.9),
                'do_sample': True,
                'pad_token_id': self.tokenizer.pad_token_id
            }
            # 동기 호출을 스레드로 실행
            outputs = await asyncio.to_thread(self.model.generate, **inputs, **gen_kwargs)
            text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return text.strip()
        except Exception as e:
            logging.error(f"콘텐츠 생성 실패: {e}")
            return ""
