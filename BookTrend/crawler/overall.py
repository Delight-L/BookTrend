# -*- coding: utf-8 -*-
"""
전체 베스트셀러 순위 크롤러
- 알라딘: https://www.aladin.co.kr/shop/common/wbest.aspx?BranchType=1&start=we
- Yes24:  https://www.yes24.com/product/category/bestseller?categoryNumber=001
분야 구분 없이 전체 판매량 순위를 수집한다.
"""
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

ALADIN_URL = "https://www.aladin.co.kr/shop/common/wbest.aspx?BranchType=1&start=we"
YES24_URL  = "https://www.yes24.com/product/category/bestseller?categoryNumber=001"
MAX_RESULTS = 10
CATEGORY = "전체"


def crawl_aladin_overall():
    try:
        res = requests.get(ALADIN_URL, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"[알라딘 전체] 요청 실패: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    titles = [a.text.strip() for a in soup.select("a.bo3")]

    if not titles:
        print("[알라딘 전체] 책 목록 없음")
        return []

    items = soup.select("div.ss_book_box")
    books = []
    if items:
        for rank, item in enumerate(items[:MAX_RESULTS], 1):
            title_tag = item.select_one("a.bo3")
            cover_tag = item.select_one("img.front_cover")
            title = title_tag.text.strip() if title_tag else ""
            cover = cover_tag.get("src", "").replace("/cover200/", "/coversum/") if cover_tag else ""
            auth_tag  = item.select_one("a[href*='AuthorSearch']")
            pub_tag   = item.select_one("a[href*='PublisherSearch'], a[href*='publishersearch']")
            author    = auth_tag.get_text(strip=True) if auth_tag else ""
            publisher = pub_tag.get_text(strip=True)  if pub_tag  else ""
            books.append({
                "store": "알라딘", "category": CATEGORY, "rank": rank,
                "title": title, "author": author, "publisher": publisher, "cover_url": cover,
            })
    else:
        for rank, (title, cover) in enumerate(zip(titles[:MAX_RESULTS], covers[:MAX_RESULTS]), 1):
            books.append({
                "store": "알라딘", "category": CATEGORY, "rank": rank,
                "title": title, "author": "", "publisher": "", "cover_url": cover,
            })

    print(f"[알라딘 전체] {len(books)}권 수집 완료")
    return books


def crawl_yes24_overall():
    for attempt in range(3):
        try:
            res = requests.get(YES24_URL, headers=HEADERS, timeout=20)
            res.raise_for_status()
            break
        except Exception as e:
            print(f"[Yes24 전체] 요청 실패 (시도 {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(3)
    else:
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.select(".itemUnit")

    if not items:
        print("[Yes24 전체] 책 목록 없음")
        return []

    books = []
    for item in items[:MAX_RESULTS]:
        rank_tag  = item.select_one("em.ico.rank")
        title_tag = item.select_one("a.gd_name")
        auth_tag  = item.select_one(".info_auth")
        img_tag   = item.select_one(".img_item img")

        if not rank_tag or not title_tag:
            continue

        rank  = int(rank_tag.text.strip())
        title = title_tag.text.strip()
        author = auth_tag.text.strip() if auth_tag else ""
        pub_tag = item.select_one(".info_pub")
        publisher = pub_tag.text.strip() if pub_tag else ""

        cover_url = ""
        if img_tag:
            src = img_tag.get("data-original") or img_tag.get("src", "")
            cover_url = src.replace("/L", "/XL").replace("/M", "/XL") if src else ""
        if not cover_url:
            link = item.select_one("a.lnk_img")
            if link and link.get("href"):
                goods_id = link["href"].split("/")[-1].split("?")[0]
                cover_url = f"https://image.yes24.com/goods/{goods_id}/XL"

        books.append({
            "store":     "예스24",
            "category":  CATEGORY,
            "rank":      rank,
            "title":     title,
            "author":    author,
            "publisher": publisher,
            "cover_url": cover_url,
        })

    print(f"[Yes24 전체] {len(books)}권 수집 완료")
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
    print("=== 전체 순위 크롤링 시작 ===")
    save_books(crawl_aladin_overall())
    time.sleep(1)
    save_books(crawl_yes24_overall())
    print("=== 전체 순위 크롤링 완료 ===")


if __name__ == "__main__":
    run()
