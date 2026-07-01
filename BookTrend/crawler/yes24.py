import requests
from bs4 import BeautifulSoup
import time
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import get_connection

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 예스24 주간 베스트셀러 카테고리 코드
# 엔드포인트: weekbestseller (사용자가 실제로 보는 주간 베스트 기준)
CATEGORIES = {
    "경제/경영": "001001025",
    "자기계발": "001001026",  # 수정: 001001021(종교) → 001001026(자기계발)
    "소설":     "001001046",  # 수정: 001001007(국내소설) → 001001046(소설전체)
    "인문":     "001001019",  # 수정: 001001020 → 001001019
    "사회과학": "001001022",  # 수정: 001001010 → 001001022 (사용자 지정 URL 기준)
    "과학":     "001001002",
    "컴퓨터/IT":"001001003",  # 수정: 001001014(보안) → 001001003(IT전체)
    "건강/취미": "001001011",
    "어린이":   "001001016",  # 수정: 001001027 → 001001016
    "에세이":   "001001047",
    "여행":     "001001009",
}

# 주간 베스트 대신 종합 베스트셀러 URL을 사용하는 카테고리
BESTSELLER_URL_OVERRIDES = {
    "여행": "https://www.yes24.com/product/category/bestseller?categoryNumber=001001009",
}

# weekbestseller: 예스24 주간 베스트 엔드포인트 (연도는 실행 시점 자동 적용)
def _make_url(category_name, code):
    if category_name in BESTSELLER_URL_OVERRIDES:
        return BESTSELLER_URL_OVERRIDES[category_name]
    year = datetime.now().year
    return (
        "https://www.yes24.com/product/category/weekbestseller"
        f"?pageNumber=1&pageSize=10&categoryNumber={code}&type=week&saleYear={year}"
)


def crawl_yes24(category_name, category_code):
    url = _make_url(category_name, category_code)
    for attempt in range(3):
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            res.raise_for_status()
            break
        except Exception as e:
            print(f"[예스24] {category_name} 요청 실패 (시도 {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(3)
    else:
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.select(".itemUnit")

    if not items:
        print(f"[예스24] {category_name} - 항목 없음")
        return []

    books = []
    for item in items[:10]:  # 판매량 상위 10권
        try:
            rank_tag = item.select_one("em.ico.rank")
            title_tag = item.select_one("a.gd_name")
            author_tag = item.select_one(".info_auth")
            publisher_tag = item.select_one(".info_pub")
            link_tag = item.select_one("a.lnk_img")

            rank = int(rank_tag.text.strip()) if rank_tag else 0
            title = title_tag.text.strip() if title_tag else "제목 없음"
            author = author_tag.text.strip() if author_tag else ""
            publisher = publisher_tag.text.strip() if publisher_tag else ""

            # 상품 ID로 표지 이미지 URL 구성
            # data-original 속성에서 직접 이미지 URL 추출 후 고화질(XL)로 변환
            cover_url = ""
            img_tag = item.select_one(".img_bdr img")
            if img_tag:
                src = img_tag.get("data-original") or img_tag.get("src", "")
                cover_url = src.replace("/L", "/XL").replace("/M", "/XL") if src else ""
            if not cover_url and link_tag and link_tag.get("href"):
                goods_id = link_tag["href"].split("/")[-1].split("?")[0]
                cover_url = f"https://image.yes24.com/goods/{goods_id}/XL"

            books.append({
                "store": "예스24",
                "category": category_name,
                "rank": rank,
                "title": title,
                "author": author,
                "publisher": publisher,
                "cover_url": cover_url,
            })
        except Exception as e:
            print(f"[예스24] 파싱 오류: {e}")
            continue

    print(f"[예스24] {category_name} - {len(books)}권 수집 완료")
    return books


def save_books(books):
    if not books:
        return
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    cursor = conn.cursor()

    for book in books:
        cursor.execute("""
            SELECT id FROM books
            WHERE store=? AND category=? AND rank=? AND DATE(crawled_at)=DATE(?)
        """, (book["store"], book["category"], book["rank"], now))

        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO books (store, category, rank, title, author, publisher, cover_url, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                book["store"], book["category"], book["rank"],
                book["title"], book["author"], book["publisher"],
                book["cover_url"], now
            ))

    conn.commit()
    conn.close()


def run():
    print("=== 예스24 크롤링 시작 ===")
    for category_name, code in CATEGORIES.items():
        books = crawl_yes24(category_name, code)
        save_books(books)
        time.sleep(1.5)
    print("=== 예스24 크롤링 완료 ===")


if __name__ == "__main__":
    run()
