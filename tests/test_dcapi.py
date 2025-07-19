import asyncio
import dc_api
import os

# 디렉토리 경로 설정
IMG_DIR = './img'

# 이미지 디렉토리가 없으면 생성
if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

async def test_dc_api():
    async with dc_api.API() as api:
        # 게시판 크롤링 및 문서 조회 테스트
        print("=== 게시판 크롤링 테스트 ===")
        async for index in api.board(board_id="programming", num=-1, start_page=1):
            print(f"제목: {index.title}")
            try:
                doc = await index.document()
                if doc:
                    print(f"내용: {doc.contents}")

                    # 이미지 다운로드 테스트
                    for image in doc.images:
                        await image.download(os.path.join(IMG_DIR, 'image'))

                    # 댓글 출력 테스트
                    async for comm in index.comments():
                        print(f"댓글: {comm.contents}")
                else:
                    print("문서가 존재하지 않거나 가져오는 데 실패했습니다.")
            except Exception as e:
                print(f"문서 조회 중 오류 발생: {e}")

        # 문서 작성 테스트
        print("\n=== 문서 작성 테스트 ===")
        try:
            doc_id = await api.write_document(
                board_id="programming",
                title="테스트 문서 제목",
                contents="테스트 문서 내용",
                name="테스트",
                password="1234"
            )
            print(f"작성한 문서 ID: {doc_id}")
        except Exception as e:
            print(f"문서 작성 중 오류 발생: {e}")

        # 문서 수정 테스트
        print("\n=== 문서 수정 테스트 ===")
        try:
            await api.modify_document(
                board_id="programming",
                document_id=doc_id,
                name="테스트",
                pw="1234",
                title="수정된 제목",
                contents="수정된 내용",
                is_minor=False
            )
            doc = await api.document(board_id="programming", document_id=doc_id)
            if doc:
                print(f"수정된 문서 제목: {doc.title}")
                print(f"수정된 문서 내용: {doc.contents}")
            else:
                print("문서가 존재하지 않거나 가져오는 데 실패했습니다.")
        except Exception as e:
            print(f"문서 수정 중 오류 발생: {e}")

        # 댓글 작성 테스트
        print("\n=== 댓글 작성 테스트 ===")
        try:
            com_id = await api.write_comment(
                board_id="programming",
                doc_id=doc_id,
                name="테스트 댓글 작성자",
                password="1234",
                contents="테스트 댓글 내용"
            )
            print(f"작성한 댓글 ID: {com_id}")
        except Exception as e:
            print(f"댓글 작성 중 오류 발생: {e}")

        # 댓글 삭제 테스트
        print("\n=== 댓글 삭제 테스트 ===")
        try:
            await api.remove_comment(board_id="programming", doc_id=doc_id, comment_id=com_id, password="1234")
        except Exception as e:
            print(f"댓글 삭제 중 오류 발생: {e}")

        # 문서 삭제 테스트
        print("\n=== 문서 삭제 테스트 ===")
        try:
            await api.remove_document(board_id="programming", doc_id=doc_id, password="1234")
            print(f"삭제한 문서 ID: {doc_id}")
        except Exception as e:
            print(f"문서 삭제 중 오류 발생: {e}")

asyncio.run(test_dc_api())
