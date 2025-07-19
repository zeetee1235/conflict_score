from openai import AsyncOpenAI
import logging

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
