import unittest
import asyncio
from database_manager import DatabaseManager

class TestDatabaseManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """
        테스트 실행 전 데이터베이스 연결을 설정합니다.
        """
        self.db_manager = DatabaseManager('test.db', 'memory')
        await self.db_manager.connect()

    async def asyncTearDown(self):
        """
        테스트 실행 후 데이터베이스 연결을 종료합니다.
        """
        await self.db_manager.close()

    async def test_save_data(self):
        """
        데이터 저장 기능을 테스트합니다.
        """
        result = await self.db_manager.save_data(board_id='test', memory_content='test content')
        self.assertTrue(result)

    async def test_load_memory(self):
        """
        메모리 로드 기능을 테스트합니다.
        """
        await self.db_manager.save_data(board_id='test', memory_content='test content')
        memory = await self.db_manager.load_memory('test')
        self.assertEqual(memory, 'test content')

if __name__ == "__main__":
    unittest.main()
