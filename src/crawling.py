#selenium 라이브러리
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

#추가 조작 라이브러리
import time
from bs4 import BeautifulSoup
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

#기타 라이브러리
import pandas as pd
import os
from selenium.common.exceptions import WebDriverException
import csv
import traceback

# 로그 설정
os.environ["MOZ_LOG"] = "socket,nsHttp:5"  # 로그을 콘솔에 출력하도록 설정
# MOZ_LOG_FILE 환경 변수를 제거하여 로그 파일 생성을 중지합니다.
os.environ.pop("MOZ_LOG_FILE", None)  # 로그 파일 생성을 중지

os.makedirs("resource", exist_ok=True)

# 현재 설치된 브라우저 버전에 맞는 드라이버 버전 지정
ser = Service(GeckoDriverManager().install())
options = Options()
# 필요에 따라 headless 모드나 다른 옵션을 추가할 수 있습니다.
# options.add_argument("--headless")
options.binary_location = '/usr/bin/firefox'
driver = webdriver.Firefox(service=ser, options=options)

# 수집할 기간 설정 (시작일 ≤ 종료일)
start_date = time.strptime("2025.6.10","%Y.%m.%d")
end_date   = time.strptime("2025.6.12","%Y.%m.%d")


#수집한 정보를 저장하는 리스트
c_gall_no_list = []
title_list = [] #제목
contents_list = [] #게시글 내용
contents_date_list = []

#수집한 정보를 저장하는 리스트
gall_no_list = [] #글 번호
reply_id = [] #답글 아이디
reply_content = [] #답글 내용
reply_date = [] #답글 등록 일자

#기본 URL
BASE = "http://gall.dcinside.com"

def parse_date(txt):
    normalized = txt.strip()
    # 시간 형식만 들어오면 오늘 날짜로 처리
    if ':' in normalized and not any(sep in normalized for sep in ['.', '/']):
        return time.localtime()
    normalized = normalized.replace('/', '.')
    parts = normalized.split('.')
    if len(parts) == 3:
        yy, mm, dd = parts
        year = yy if len(yy) == 4 else '20' + yy
    elif len(parts) == 2:
        mm, dd = parts
        year = str(start_date.tm_year)  # MM.DD만 나올 땐 수집 시작 연도로 설정
    else:
        raise ValueError(f"Unknown date format: {txt}")
    mm = mm.zfill(2); dd = dd.zfill(2)
    return time.strptime(f"{year}.{mm}.{dd}", "%Y.%m.%d")

# 크롤 시작 페이지를 최신 글(1번 페이지)부터 순차 조회하도록 수정
start_page = 1
Flag = True

# -- CSV 파일 열기 및 헤더 삽입 (append 모드) --
contents_csv = "resource/contents.csv"
need_header = not os.path.exists(contents_csv) or os.path.getsize(contents_csv) == 0
contents_f = open(contents_csv, "a", newline='', encoding='utf8')
contents_writer = csv.writer(contents_f)


if need_header:
    contents_writer.writerow(["id","title","contents","date"])

reply_csv = "resource/reply.csv"
need_header2 = not os.path.exists(reply_csv) or os.path.getsize(reply_csv) == 0
reply_f = open(reply_csv, "a", newline='', encoding='utf8')
reply_writer = csv.writer(reply_f)


if need_header2:
    reply_writer.writerow(["id","reply_id","reply_content","reply_date"])


if __name__ == "__main__":
    print(f"[INFO] 크롤링을 시작합니다. 기간: {time.strftime('%Y.%m.%d', start_date)} ~ {time.strftime('%Y.%m.%d', end_date)}")
    print(f"[DEBUG] 크롤링 시작 페이지: {start_page}")
    print(f"[DEBUG] 크롤링 대상 URL: {BASE}/board/lists/?id=programming&page={start_page}")
    # 크롤링 시작
    while Flag:  # 게시글의 페이지마다 loop를 수행
        base_url = BASE + '/board/lists/?id=programming&page=' + str(start_page)
        print(base_url)

        try:
            driver.get(base_url)
            sleep(3)
            page_source = driver.page_source
        except WebDriverException as e:
            print(f"[ERROR] WebDriver error on list page: {e}")
            traceback.print_exc()
            driver.quit()
            driver = webdriver.Firefox(service=ser, options=options)
            continue
        except Exception as e:
            print(f"[ERROR] 리스트 페이지 로딩 실패: {e}")
            traceback.print_exc()
            continue

        soup = BeautifulSoup(page_source, "html.parser")
        # 게시글 목록을 담고 있는 tbody.listwrap2 내부의 tr 태그를 모두 선택
        body = soup.find('tbody', class_='listwrap2')
        if not body:
            start_page += 1
            continue
        article_list = body.find_all('tr')
        if not article_list:
            start_page += 1
            continue

        # 페이지단위 날짜 필터 (0번 = 가장 오래된, -1번 = 가장 최신)
        oldest_date = parse_date(article_list[0].find("td",{"class":"gall_date"}).text)
        newest_date = parse_date(article_list[-1].find("td",{"class":"gall_date"}).text)
        print(f"[DEBUG] Page {start_page}: oldest={time.strftime('%Y.%m.%d', oldest_date)}, newest={time.strftime('%Y.%m.%d', newest_date)}")

        # 페이지 내 모든 글이 기간 이전(너무 오래된) → 크롤 종료
        if newest_date < start_date:
            print("수집을 종료합니다.")
            break
        # 페이지 내 모든 글이 기간 이후(너무 최신) → 다음 페이지로
        if oldest_date > end_date:
            start_page += 1
            continue

        for article in article_list:
            art_date = parse_date(article.find("td",{"class":"gall_date"}).text)
            # 개별 글이 수집 기간 외면 스킵
            if art_date < start_date or art_date > end_date:
                continue
            
            # 제목과 종류 추출 (gall_subject 셀 안의 첫 번째 <a>)
            subj_cell = article.find("td", class_=lambda v: v and "gall_tit ub-word" in v)
            if not subj_cell:
                continue
            link = subj_cell.find("a", href=True)
            if not link:
                continue
            title = link.text.strip()
            
            #head = subj_cell.get_text(strip=True).replace(title, "").strip()
            
            
            
            gall_id = article.find("td",{"class" : "gall_num"}).text.strip() #글 id 추출

            if gall_id not in ['설문','AD','공지']: #사용자들이 쓴 글이 목적이므로 광고/설문/공지 제외
                    
                # 게시글 번호
                gall_id = article.find("td",{"class" : "gall_num"}).text

                # 중복 방지: 저장 직후 체크
                if gall_id in c_gall_no_list:
                    continue
                
                #각 게시글의 주소를 찾기 -> 내용 + 댓글 수집 목적
                tag = article.find('a',href = True)
                content_url = BASE + tag['href']
                
                #게시글 load
                try:
                    driver.get(content_url)
                    sleep(3)
                    print(f"Loading content: {content_url}")
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "write_div"))
                    )
                    contents_soup = BeautifulSoup(driver.page_source, "html.parser")
                    contents = contents_soup.find('div', {"class": "write_div"}).text
                except Exception as e:
                    print(f"[ERROR] 게시글 로딩 실패: {content_url} → {e}")
                    traceback.print_exc()
                    continue

                #게시글의 작성 날짜
                raw = article.find("td",{"class":"gall_date"}).text
                c_date = "20" + raw.replace('/', '.')

                #게시글 제목과 내용을 수집
                c_gall_no_list.append(gall_id)
                title_list.append(title)
                contents_list.append(contents)
                contents_date_list.append(c_date)
                
                # 즉시 contents.csv에 기록
                contents_writer.writerow([gall_id, title, contents, c_date])
                contents_f.flush()
                print(f"[INFO] Saved post → id: {gall_id}, title: {title}")

                # 댓글 리스트를 직접 찾아서 순회
                comments = contents_soup.select(f"#comment_wrap_{gall_id} li.ub-content")
                for comment in comments:
                    try:
                        user_name       = comment.find("span", class_="nickname").text.strip()
                        user_reply_date = comment.find("span", class_="date_time").text.strip()
                        user_reply      = comment.find("p", class_="usertxt").text.strip()
                        reply_writer.writerow([gall_id, user_name, user_reply, user_reply_date])
                        reply_f.flush()
                        print(f"[INFO] Saved reply → post_id: {gall_id}, reply_id: {user_name}")
                    except Exception as e:
                        print(f"[ERROR] 댓글 파싱 실패: post_id={gall_id} → {e}")
                        traceback.print_exc()
                        continue

        #다음 게시글 목록 페이지로 넘어가기
        start_page += 1
        

    # 파일 닫기
    contents_f.close()
    reply_f.close()
    # 크롤링 드라이버 종료
    driver.quit()
    
    print(f"[INFO] 크롤링 완료. 수집된 게시글 수: {len(c_gall_no_list)}")
    print(f"[INFO] 게시글 정보 저장 위치: {contents_csv}")
    print(f"[INFO] 댓글 정보 저장 위치: {reply_csv}")
    print("[INFO] 크롤링이 완료되었습니다.")


