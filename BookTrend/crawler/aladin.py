# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import time
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# .env 파일에서 API 키 로드 (코드에 절대 하드코딩 금지)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
TTB_KEY = os.getenv("ALADIN_TTB_KEY")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import get_connection

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# TTB API 사용 카테고리 (CategoryId 기준)
TTB_CATEGORIES = {
    "경제/경영": "170",
    "자기계발": "336",
    "소설": "1",
    "인문": "656",
    "사회과학": "798",
    "과학": "987",
    "컴퓨터/IT": "351",
    "에세이": "51371",
    "여행": "1196",
}

# 웹 직접 크롤링 카테고리 (사용자가 지정한 정확한 URL)
WEB_CATEGORIES = {
    "건강/취미": "https://www.aladin.co.kr/shop/common/wbest.aspx?BestType=Bestseller&BranchType=1&CID=55890",
    "어린이":   "https://www.aladin.co.kr/shop/common/wbest.aspx?BestType=Bestseller&BranchType=1&CID=1108",
}

# TTB API 엔드포인트 (API 키는 환경변수에서만 읽음)
TTB_URL = (
    "http://www.aladin.co.kr/ttb/api/ItemList.aspx"
    "?ttbkey={key}&QueryType=Bestseller&MaxResults=10"
    "&SearchTarget=Book&CategoryId={cid}&Output=JS&Version=20131101"
)


def crawl_aladin(category_name, cid):
    if not TTB_KEY:
        print("[알라딘] API 키 없음 — .env 파일에 ALADIN_TTB_KEY를 설정하세요")
        return []

    url = TTB_URL.format(key=TTB_KEY, cid=cid)
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"[알라딘] {category_name} 요청 실패: {e}")
        return []

    items = data.get("item", [])
    if not items:
        print(f"[알라딘] {category_name} - 항목 없음")
        return []

    books = []
    for rank, item in enumerate(items[:10], start=1):
        books.append({
            "store": "알라딘",
            "category": category_name,
            "rank": rank,
            "title": item.get("title", "").strip(),
            "author": item.get("author", "").strip(),
            "publisher": item.get("publisher", "").strip(),
            "cover_url": item.get("cover", ""),
        })

    print(f"[알라딘] {category_name} - {len(books)}권 수집 완료")
    return books


def crawl_aladin_web(category_name, url, max_results=10):
    """
    wbest.aspx 페이지 직접 크롤링.
    a.bo3 = 제목, .ss_f_g2 = 저자|출판사 정보
    """
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"[알라딘] {category_name} 웹 요청 실패: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.select("div.ss_book_box")

    if not items:
        # fallback: 제목만
        titles = [a.text.strip() for a in soup.select("a.bo3")]
        covers = [
            img.get("src", "").replace("/cover200/", "/coversum/")
            for img in soup.select("img.front_cover")
        ]
        books = []
        for rank, (title, cover) in enumerate(zip(titles[:max_results], covers[:max_results]), start=1):
            books.append({
                "store": "알라딘", "category": category_name, "rank": rank,
                "title": title, "author": "", "publisher": "", "cover_url": cover,
            })
        print(f"[알라딘] {category_name} - {len(books)}권 수집 완료 (웹/fallback)")
        return books

    books = []
    for rank, item in enumerate(items[:max_results], start=1):
        title_tag = item.select_one("a.bo3")
        cover_tag = item.select_one("img.front_cover")

        title = title_tag.text.strip() if title_tag else ""
        cover = cover_tag.get("src", "").replace("/cover200/", "/coversum/") if cover_tag else ""

        auth_tag = item.select_one("a[href*='AuthorSearch']")
        pub_tag  = item.select_one("a[href*='PublisherSearch'], a[href*='publishersearch']")
        author    = auth_tag.get_text(strip=True) if auth_tag else ""
        publisher = pub_tag.get_text(strip=True)  if pub_tag  else ""

        books.append({
            "store": "알라딘", "category": category_name, "rank": rank,
            "title": title, "author": author, "publisher": publisher, "cover_url": cover,
        })

    print(f"[알라딘] {category_name} - {len(books)}권 수집 완료 (웹)")
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
    print("=== 알라딘 크롤링 시작 ===")
    for category_name, cid in TTB_CATEGORIES.items():
        books = crawl_aladin(category_name, cid)
        save_books(books)
        time.sleep(1)
    for category_name, web_url in WEB_CATEGORIES.items():
        books = crawl_aladin_web(category_name, web_url)
        save_books(books)
        time.sleep(1)
    print("=== 알라딘 크롤링 완료 ===")


if __name__ == "__main__":
    run()
