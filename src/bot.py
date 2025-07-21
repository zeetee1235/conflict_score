import logging
import re
import asyncio
import time
from collections import Counter
from utils import handle_exceptions, sanitize_text, clean_title

class DcinsideBot:
    def __init__(self, api_manager, db_managers, persona, settings):
        """
        DcinsideBot 클래스를 초기화합니다.

        :param api_manager: DCInside API 관리 객체
        :param db_managers: 데이터베이스 관리 객체들
        :param persona: 봇의 페르소나
        :param settings: 봇 설정
        """
        self.api_manager = api_manager
        self.crawling_db = db_managers['crawling']
        self.data_db = db_managers['data']
        self.memory_db = db_managers['memory']
        
        self.persona = persona
        self.settings = settings
        self.write_article_enabled = settings.get('write_article_enabled', True)
        self.write_comment_enabled = settings.get('write_comment_enabled', True)
        self.board_id = settings['board_id']
        self.username = settings['username']
        self.password = settings['password']

    @handle_exceptions
    async def get_trending_topics(self):
        """
        최신 트렌딩 토픽을 가져옵니다.

        :return: 최신 토픽의 카운터 객체
        """
        articles = [article async for article in self.api_manager.api.board(
            board_id=self.board_id,
            num=self.settings['crawl_article_count']
        )]
        title_list = [article.title for article in articles]
        return Counter(title_list)

    @handle_exceptions
    async def record_gallery_information(self):
        """
        갤러리 정보를 메모리에 기록합니다.
        """
        if not self.settings.get('record_memory_enabled', True):
            return

        articles = [article async for article in self.api_manager.api.board(
            board_id=self.board_id,
            num=self.settings['crawl_article_count']
        )]
        memory_content = await self.generate_memory_from_crawling(articles)
        await self.memory_db.save_data(
            board_id=self.board_id,
            memory_content=memory_content
        )
            
    async def generate_memory_from_crawling(self, articles):
        crawling_info = "\n".join([f"제목: {article.title}, 저자: {article.author}" for article in articles])
        prompt = f"""
        {self.persona}

        디시인사이드 갤러리에서 크롤링한 정보를 바탕으로, {self.persona} 페르소나에 맞춰서 메모리를 작성해줘.

        크롤링 정보:
        {crawling_info}
        """
        content = await self.gpt_api_manager.generate_content(prompt)
        
        if content is None:
            logging.error("GPT API returned None content")
            return ""

        return sanitize_text(content)

    async def write_article(self, trending_topics, memory_data=None):
        if not self.write_article_enabled:
            logging.info("게시글 작성이 비활성화되어 있습니다.")
            return

        try:
            prompt = self.create_article_prompt(trending_topics, memory_data)

            title, content = await self.gpt_api_manager.generate_text(prompt)

            await self.api_manager.write_document(title, content)

            logging.info(f"게시글 작성 완료: {title}")
            await self.memory_db.save_data(self.board_id, "article", f"작성한 글: {title}")

        except Exception as e:
            logging.error(f"게시글 작성 중 오류 발생: {e}")

    @handle_exceptions
    async def write_comment(self, doc_id, document_title):
        """
        댓글을 작성합니다.

        :param doc_id: 문서 ID
        :param document_title: 문서 제목
        """
        if not self.write_comment_enabled:
            logging.info("댓글 작성이 비활성화되어 있습니다.")
            return

        try:
            prompt = self.create_comment_prompt(document_title)
            _, comment_content = await self.gpt_api_manager.generate_text(prompt)

            await self.api_manager.write_comment(doc_id, comment_content)

            logging.info(f"댓글 작성 완료: {comment_content} (글: {document_title})")
            await self.memory_db.save_data(self.board_id, "comment", f"작성한 댓글: {comment_content} (글: {document_title})")

        except Exception as e:
            logging.error(f"댓글 작성 중 오류 발생: {e}")

    def create_article_prompt(self, trending_topics, memory_data):
        """
        게시글 작성을 위한 프롬프트를 생성합니다.

        :param trending_topics: 트렌딩 토픽
        :param memory_data: 메모리 데이터
        :return: 생성된 프롬프트
        """
        return (
            f"페르소나: {self.persona}\n\n"
            f"최신 토픽: {trending_topics}\n\n"
            f"메모리: {memory_data}\n\n"
            "위 정보를 바탕으로 DCinside 게시글의 제목과 내용을 생성해줘. "
            "응답은 '제목: [생성된 제목]\n내용: [생성된 내용]' 형식이어야 합니다."
        )

    def create_comment_prompt(self, document_title):
        """
        댓글 작성을 위한 프롬프트를 생성합니다.

        :param document_title: 문서 제목
        :return: 생성된 프롬프트
        """
        return (
            f"페르소나: {self.persona}\n\n"
            f"게시글 제목: {document_title}\n\n"
            "위 게시글에 대한 댓글을 생성해줘. "
            "응답은 '제목: [임의의 텍스트]\n내용: [생성된 댓글 내용]' 형식이어야 합니다."
        )
        
    async def write_comment(self, document_id, article_title):
        if not self.write_comment_enabled:
            return None

        prompt = f"""
        {self.persona}

        다음 글에 대한 댓글을 페르소나에 충실하게 작성해줘.

        글 제목: {article_title}

        댓글은 아래 형식으로 작성해줘:
        댓글: [댓글 텍스트]
        """
        while True:
            try:
                content = await self.gpt_api_manager.generate_content(prompt)

                if not content:
                    raise ValueError("생성된 콘텐츠가 비어있습니다.")

                # "댓글:"으로 시작하는 텍스트를 파싱하여 추출
                comment_match = re.search(r"댓글:\s*(.*)", content)
                if not comment_match:
                    raise ValueError("댓글 텍스트를 찾을 수 없습니다.")

                comment_content = sanitize_text(comment_match.group(1)).strip()

                comm_id = await self.api_manager.write_comment(
                    document_id=document_id,
                    content=comment_content
                )

                first_sentence = comment_content.split('\n')[0]

                await self.data_db.save_data(
                    content_type="comment",
                    doc_id=document_id,
                    content=first_sentence,
                    board_id=self.board_id
                )

                return True
            except Exception as e:
                logging.error(f"댓글 작성 실패: {e}")
                await asyncio.sleep(5)