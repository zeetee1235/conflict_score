import logging
import re
import asyncio
import time
from collections import Counter
from utils import handle_exceptions, sanitize_text, clean_title

class DcinsideBot:
    def __init__(self, api_manager, db_managers, gpt_api_manager, persona, settings):
        """
        DcinsideBot 클래스를 초기화합니다.

        :param api_manager: DCInside API 관리 객체
        :param db_managers: 데이터베이스 관리 객체들
        :param gpt_api_manager: GPT API 관리 객체
        :param persona: 봇의 페르소나
        :param settings: 봇 설정
        """
        self.api_manager = api_manager
        self.crawling_db = db_managers['crawling']
        self.data_db = db_managers['data']
        self.memory_db = db_managers['memory']
        self.gpt_api_manager = gpt_api_manager
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
            return None

        top_trending_topics = [topic[0] for topic in trending_topics.most_common(3)]

        prompt = f"""
        {self.persona} 페르소나 규칙 꼭 지키기.

        {self.board_id} 갤러리에 어울리는 흥미로운 글 제목과 내용을 한 번에 작성해줘.
        최근 유행하는 토픽을 참고하여 제목과 글을 구성하고, 페르소나에 맞춰 작성해줘.

        최근 {self.board_id} 갤러리에서 유행하는 토픽은 다음과 같습니다:
        {trending_topics}

        특히 다음 토픽들을 중심으로 글 내용을 구성해줘:
        {', '.join(top_trending_topics)}

        갤러리의 최근 정보를 참고하여 글 내용을 더욱 풍성하게 만들어줘:
        {memory_data}
        제목과 내용은 아래 형식으로 작성해줘:
        제목: [제목 텍스트]
        내용: [내용 텍스트]
        """
        while True:
            try:
                content = await self.gpt_api_manager.generate_content(prompt)
                
                if not content:
                    raise ValueError("생성된 콘텐츠가 비어있습니다.")

                # 제목과 내용을 분리
                title_match = re.search(r"제목:\s*(.*)", content)
                content_match = re.search(r"내용:\s*(.*)", content)

                if not title_match or not content_match:
                    raise ValueError("제목 또는 내용을 찾을 수 없습니다.")

                title = sanitize_text(title_match.group(1))
                content = sanitize_text(content_match.group(1))

                doc_id = await self.api_manager.write_document(
                    title=title,
                    content=content
                )

                await self.data_db.save_data(
                    content_type="article",
                    doc_id=doc_id,
                    content=title,
                    board_id=self.board_id
                )

                return doc_id, title
            except Exception as e:
                logging.error(f"글 작성 실패: {e}")
                await asyncio.sleep(self.settings['article_interval'])

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