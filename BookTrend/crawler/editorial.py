# -*- coding: utf-8 -*-
"""
알라딘 편집장의 선택 크롤러
- 대상: https://www.aladin.co.kr/weeklyeditorialmeeting/detail.aspx
- 3~4일 주기로 4권씩 업데이트됨
- 각 회차 도서는 #...CommentReview 링크를 가지므로 이걸로 현재 배치 식별
"""
import re
import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

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

EDITORIAL_URL = "https://www.aladin.co.kr/weeklyeditorialmeeting/detail.aspx"


def _get_current_item_ids() -> list[str]:
    """
    편집장의 선택 페이지에서 현재 배치(4권)의 ItemId 목록 반환.
    각 현재 배치 도서는 '#...CommentReview' anchor가 붙은 링크를 가짐.
    """
    r = requests.get(EDITORIAL_URL, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    # CommentReview 링크에서 ItemId 추출 (현재 배치 4권 식별자)
    review_ids: list[str] = []
    for a in soup.find_all("a", href=re.compile(r"ItemId=\d+.*CommentReview")):
        m = re.search(r"ItemId=(\d+)", a["href"])
        if m:
            item_id = m.group(1)
            if item_id not in review_ids:
                review_ids.append(item_id)

    return review_ids


def _fetch_book_info(item_id: str) -> dict | None:
    """TTB API + 상품 페이지 스크래핑으로 도서 정보 조합."""
    if not TTB_KEY:
        print(f"[편집장] TTB_KEY 없음 — ItemId {item_id} 스킵")
        return None

    lu_url = (
        f"http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
        f"?ttbkey={TTB_KEY}&itemIdType=ItemId&ItemId={item_id}"
        f"&output=JS&Version=20131101"
    )
    try:
        lr = requests.get(lu_url, timeout=10)
        it = lr.json().get("item", [{}])[0]
        if not it:
            return None
    except Exception as e:
        print(f"[편집장] TTB API 오류 (ItemId={item_id}): {e}")
        return None

    # 상품 페이지에서 편집장 코멘트 + MD 정보 스크래핑
    product_url = f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}"
    editorial_text = ""
    md_info = ""
    try:
        pr = requests.get(product_url, headers=HEADERS, timeout=15)
        pr.encoding = "utf-8"
        psoup = BeautifulSoup(pr.text, "html.parser")

        for box in psoup.select(".Ere_prod_mconts_box"):
            if "편집장의 선택" in box.get_text():
                r_div = box.select_one(".Ere_prod_mconts_R")
                if r_div:
                    editorial_text = r_div.get_text(separator=" ").strip()
                break

        md_el = psoup.select_one(".Ere_sub_blue.Ere_textR.Ere_PT10")
        if md_el:
            md_info = md_el.get_text(strip=True).lstrip("- ").strip()
    except Exception as e:
        print(f"[편집장] 상품 페이지 스크래핑 오류 (ItemId={item_id}): {e}")

    cover = it.get("cover", "").replace("/coversum/", "/cover500/")

    return {
        "store":         "알라딘",
        "title":         it.get("title", ""),
        "author":        it.get("author", ""),
        "publisher":     it.get("publisher", ""),
        "cover_url":     cover,
        "editorial_text": editorial_text,
        "md_info":       md_info,
        "link":          f"https://www.aladin.co.kr/shop/wproduct.aspx?ItemId={item_id}",
    }


def crawl_aladin_editorial() -> list[dict]:
    """현재 배치 4권 정보를 모두 반환."""
    item_ids = _get_current_item_ids()
    if not item_ids:
        print("[알라딘 편집장] 현재 배치 ItemId 추출 실패")
        return []

    print(f"[알라딘 편집장] 현재 배치 ItemId: {item_ids}")

    books = []
    for item_id in item_ids:
        book = _fetch_book_info(item_id)
        if book and book["title"]:
            books.append(book)
            print(f"[알라딘 편집장] 수집: {book['title'][:40]}")

    return books


def save_editorial(book: dict):
    """
    편집장 추천 도서를 DB에 저장.
    동일 제목은 서점 불문 전체 기간 기준으로 중복 저장하지 않음
    (추천 배치가 바뀌지 않는 한 재크롤링해도 추가 저장 안 됨).
    """
    if not book or not book.get("title"):
        return
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    exists = conn.execute(
        "SELECT id FROM editorial WHERE store=? AND title=?",
        (book["store"], book["title"]),
    ).fetchone()
    if exists is None:
        conn.execute(
            """
            INSERT INTO editorial
              (store, title, author, publisher, cover_url,
               editorial_text, md_info, link, crawled_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                book["store"], book["title"], book.get("author", ""),
                book.get("publisher", ""), book.get("cover_url", ""),
                book.get("editorial_text", ""), book.get("md_info", ""),
                book.get("link", ""), now,
            ),
        )
        conn.commit()
        print(f"[편집장] DB 저장: {book['title'][:40]}")
    else:
        print(f"[편집장] 이미 저장됨 (스킵): {book['title'][:40]}")
    conn.close()


def run() -> list[dict]:
    print("=== 알라딘 편집장의 선택 크롤링 시작 ===")
    books = crawl_aladin_editorial()
    for book in books:
        save_editorial(book)
    print(f"=== 완료: {len(books)}권 처리 ===")
    return books


if __name__ == "__main__":
    import json, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
