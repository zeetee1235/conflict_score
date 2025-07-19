import aiosqlite
import os
import logging

class DatabaseManager:
    def __init__(self, db_file: str, db_type: str):
        """
        데이터베이스 관리자를 초기화합니다.

        :param db_file: 데이터베이스 파일 이름
        :param db_type: 데이터베이스 유형 (crawling, data, memory)
        """
        self.db_file = os.path.join(".", db_file)
        self.db_type = db_type
        self.conn = None

    async def connect(self) -> None:
        """
        데이터베이스에 비동기적으로 연결하고 필요한 테이블을 생성합니다.
        """
        try:
            # 데이터베이스 디렉토리 생성
            db_dir = os.path.dirname(self.db_file)
            os.makedirs(db_dir, exist_ok=True)

            # 데이터베이스 파일이 존재하지 않으면 생성
            if not os.path.exists(self.db_file):
                open(self.db_file, 'a').close()

            # 데이터베이스 연결
            self.conn = await aiosqlite.connect(self.db_file)
            await self.create_tables()
        except Exception as e:
            logging.error(f"데이터베이스 연결 실패: {e}")
            self.conn = None

    async def create_tables(self) -> None:
        """
        데이터베이스 유형에 따라 필요한 테이블을 생성합니다.
        """
        if self.conn is None:
            logging.error("데이터베이스 연결이 설정되지 않았습니다.")
            return

        try:
            cursor = await self.conn.cursor()
            if self.db_type == "crawling":
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS crawled_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        board_id TEXT,
                        article_title TEXT,
                        author_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            elif self.db_type == "data":
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS generated_content (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content_type TEXT,
                        doc_id TEXT,
                        content TEXT,
                        board_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            elif self.db_type == "memory":
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS gallery_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        board_id TEXT,
                        memory_content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            await self.conn.commit()
        except Exception as e:
            logging.error(f"테이블 생성 실패: {e}")

    async def save_data(self, **kwargs) -> None:
        """
        데이터베이스에 데이터를 저장합니다.

        :param kwargs: 데이터베이스에 저장할 데이터 (키워드 인자)
        """
        if self.conn is None:
            logging.error("데이터베이스 연결이 설정되지 않았습니다.")
            return

        try:
            cursor = await self.conn.cursor()
            if self.db_type == "crawling":
                await cursor.execute('''
                    INSERT INTO crawled_data (board_id, article_title, author_id)
                    VALUES (:board_id, :article_title, :author_id)
                ''', kwargs)
            elif self.db_type == "data":
                await cursor.execute('''
                    INSERT INTO generated_content (content_type, doc_id, content, board_id)
                    VALUES (:content_type, :doc_id, :content, :board_id)
                ''', kwargs)
            elif self.db_type == "memory":
                await cursor.execute('''
                    INSERT INTO gallery_memory (board_id, memory_content)
                    VALUES (:board_id, :memory_content)
                ''', kwargs)
            await self.conn.commit()
        except Exception as e:
            logging.error(f"데이터 저장 실패: {e}")

    async def load_memory(self, board_id: str) -> str:
        """
        'memory' 데이터베이스에서 메모리를 로드합니다.

        :param board_id: 메모리를 로드할 게시판 ID
        :return: 로드된 메모리 내용
        """
        if self.conn is None:
            logging.error("데이터베이스 연결이 설정되지 않았습니다.")
            return ""

        if self.db_type != "memory":
            logging.warning("메모리 데이터는 'memory' 데이터베이스에서만 로드할 수 있습니다.")
            return ""

        try:
            cursor = await self.conn.cursor()
            await cursor.execute('''
                SELECT memory_content
                FROM gallery_memory
                WHERE board_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (board_id,))
            row = await cursor.fetchone()
            return row[0] if row else ""
        except Exception as e:
            logging.error(f"메모리 로드 실패: {e}")
            return ""

    async def close(self) -> None:
        """
        데이터베이스 연결을 닫습니다.
        """
        if self.conn:
            try:
                await self.conn.close()
            except Exception as e:
                logging.error(f"데이터베이스 연결 닫기 실패: {e}")
        else:
            logging.warning("닫을 데이터베이스 연결이 없습니다.")