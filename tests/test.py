import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from time import sleep

# Selenium 설정 (Firefox 예시)
options = Options()
# options.add_argument("--headless")  # 브라우저 창 없이 실행
ser = Service(GeckoDriverManager().install())
driver = webdriver.Firefox(service=ser, options=options)

url = "https://gall.dcinside.com/board/view/?id=programming&no=2864098&page=1"
driver.get(url)
# 페이지가 완전히 로드되도록 약간의 대기 시간을 주기
sleep(3)

# 전체 HTML 코드 추출
full_html = driver.page_source

# 저장할 파일 경로 지정 (프로젝트 루트의 main_page_html.txt)
save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../user_page_html.txt"))
with open(save_path, "w", encoding="utf-8") as f:
    f.write(full_html)
print(f"HTML saved to {save_path}")

driver.quit()
