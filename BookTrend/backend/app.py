# -*- coding: utf-8 -*-
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sys, os, threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import init_db, get_connection
from utils.normalize import normalize_title

app = Flask(__name__)
CORS(app)  # 프론트엔드에서 API 호출 허용


def common_norm_set(rows_a, rows_b):
    """두 row 리스트에서 정규화 주제목이 겹치는 집합을 반환."""
    norms_a = {normalize_title(r["title"]) for r in rows_a}
    norms_b = {normalize_title(r["title"]) for r in rows_b}
    return norms_a & norms_b


# ─── 크롤링 상태 ─────────────────────────────────────────────
_crawl_status = {"running": False, "message": "대기 중"}
_editorial_cache = {"data": None}  # 편집장 추천 메모리 캐시 (list[dict])

def _run_crawl_background():
    global _crawl_status
    try:
        from crawler.aladin import run as aladin_run
        from crawler.yes24 import run as yes24_run
        from analysis.trend_analyzer import analyze_trends

        from crawler.overall import run as overall_run

        _crawl_status = {"running": True, "message": "알라딘 수집 중..."}
        aladin_run()
        _crawl_status = {"running": True, "message": "예스24 수집 중..."}
        yes24_run()
        _crawl_status = {"running": True, "message": "전체 순위 수집 중..."}
        overall_run()
        _crawl_status = {"running": True, "message": "편집장 추천 수집 중..."}
        from crawler.editorial import run as editorial_run
        _editorial_cache["data"] = editorial_run()
        _crawl_status = {"running": True, "message": "트렌드 분석 중..."}
        analyze_trends()
        _crawl_status = {"running": False, "message": "완료"}
    except Exception as e:
        _crawl_status = {"running": False, "message": f"오류: {e}"}


@app.route("/api/crawl", methods=["POST"])
def crawl():
    global _crawl_status
    if _crawl_status["running"]:
        return jsonify({"status": "running", "message": "이미 크롤링 중입니다."})
    t = threading.Thread(target=_run_crawl_background, daemon=True)
    t.start()
    return jsonify({"status": "started", "message": "크롤링을 시작했습니다."})


@app.route("/api/crawl/status")
def crawl_status():
    return jsonify(_crawl_status)


# ─── 베스트셀러 목록 ─────────────────────────────────────────
_LATEST_DATE_SQL = "(SELECT MAX(DATE(crawled_at)) FROM books)"


@app.route("/api/books")
def get_books():
    """
    쿼리 파라미터:
      store    : 알라딘 | 예스24 (없으면 전체)
      category : 분야명 (없으면 전체)
    """
    store = request.args.get("store")
    category = request.args.get("category")

    conn = get_connection()
    query = (
        "SELECT store, category, rank, title, author, publisher, cover_url FROM books"
        f" WHERE DATE(crawled_at)={_LATEST_DATE_SQL}"
    )
    params = []

    if store:
        query += " AND store=?"
        params.append(store)
    if category:
        query += " AND category=?"
        params.append(category)

    query += " ORDER BY category, store, rank"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    books = [dict(row) for row in rows]
    return jsonify(books)


# ─── 분야 목록 ───────────────────────────────────────────────
@app.route("/api/categories")
def get_categories():
    conn = get_connection()
    rows = conn.execute(
        f"SELECT DISTINCT category FROM books WHERE DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY category"
    ).fetchall()
    conn.close()
    return jsonify([r[0] for r in rows])


# ─── 분야별 트렌드 키워드 ────────────────────────────────────
@app.route("/api/trends")
def get_trends():
    """
    쿼리 파라미터:
      category : 분야명 (없으면 전체)
      limit    : 키워드 개수 (기본 15)
    """
    category = request.args.get("category")
    limit = int(request.args.get("limit", 15))

    conn = get_connection()
    if category:
        rows = conn.execute(
            "SELECT keyword, frequency FROM trends WHERE category=? ORDER BY frequency DESC LIMIT ?",
            (category, limit)
        ).fetchall()
        result = {"category": category, "keywords": [dict(r) for r in rows]}
    else:
        rows = conn.execute(
            "SELECT category, keyword, frequency FROM trends ORDER BY category, frequency DESC"
        ).fetchall()
        result = {}
        for r in rows:
            cat = r["category"]
            if cat not in result:
                result[cat] = []
            if len(result[cat]) < limit:
                result[cat].append({"keyword": r["keyword"], "frequency": r["frequency"]})

    conn.close()
    return jsonify(result)


# ─── 서점별 순위 비교 ────────────────────────────────────────
@app.route("/api/compare")
def get_compare():
    category = request.args.get("category")
    conn = get_connection()

    if category:
        cats = [category]
    else:
        cats = [r[0] for r in conn.execute(
            f"SELECT DISTINCT category FROM books WHERE category != '전체' AND DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY category"
        ).fetchall()]

    result = []
    for cat in cats:
        aladin = conn.execute(
            f"SELECT rank, title, author, cover_url FROM books WHERE store='알라딘' AND category=? AND DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY rank",
            (cat,)
        ).fetchall()
        yes24 = conn.execute(
            f"SELECT rank, title, author, cover_url FROM books WHERE store='예스24' AND category=? AND DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY rank",
            (cat,)
        ).fetchall()

        common_norms = common_norm_set(aladin, yes24)

        # 양쪽 모두 TOP5인 책의 정규화 제목 집합
        top5_norms = {
            normalize_title(r["title"]) for r in aladin if r["rank"] <= 5
        } & {
            normalize_title(r["title"]) for r in yes24  if r["rank"] <= 5
        }

        def book_flags(r):
            norm = normalize_title(r["title"])
            return dict(r) | {
                "common":      norm in common_norms,
                "top5_common": norm in top5_norms,
            }

        result.append({
            "category": cat,
            "aladin": [book_flags(r) for r in aladin],
            "yes24":  [book_flags(r) for r in yes24],
        })

    conn.close()
    return jsonify(result)


# ─── 전체 판매 순위 ──────────────────────────────────────────
@app.route("/api/overall")
def get_overall():
    conn = get_connection()
    aladin = conn.execute(
        f"SELECT rank, title, author, cover_url FROM books WHERE store='알라딘' AND category='전체' AND DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY rank"
    ).fetchall()
    yes24 = conn.execute(
        f"SELECT rank, title, author, cover_url FROM books WHERE store='예스24' AND category='전체' AND DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY rank"
    ).fetchall()

    common_norms = common_norm_set(aladin, yes24)

    conn.close()
    return jsonify({
        "aladin": [dict(r) | {"common": normalize_title(r["title"]) in common_norms} for r in aladin],
        "yes24":  [dict(r) | {"common": normalize_title(r["title"]) in common_norms} for r in yes24],
    })


# ─── 두 서점 공통 베스트셀러 ────────────────────────────────
@app.route("/api/common")
def get_common():
    conn = get_connection()
    cats = [r[0] for r in conn.execute(
        f"SELECT DISTINCT category FROM books WHERE category != '전체' AND DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY category"
    ).fetchall()]

    result = []
    for cat in cats:
        aladin = conn.execute(
            f"SELECT rank, title, author, cover_url FROM books WHERE store='알라딘' AND category=? AND DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY rank",
            (cat,)
        ).fetchall()
        yes24 = conn.execute(
            f"SELECT rank, title, author, cover_url FROM books WHERE store='예스24' AND category=? AND DATE(crawled_at)={_LATEST_DATE_SQL} ORDER BY rank",
            (cat,)
        ).fetchall()

        # 예스24 정규화 제목 → row 매핑
        yes24_norm_map = {normalize_title(r["title"]): r for r in yes24}

        for a in aladin:
            a_norm = normalize_title(a["title"])
            if a_norm in yes24_norm_map:
                b = yes24_norm_map[a_norm]
                result.append({
                    "category":    cat,
                    "title":       a["title"],
                    "author":      a["author"],
                    "aladin_rank": a["rank"],
                    "yes24_rank":  b["rank"],
                    "cover_url":   a["cover_url"],
                })

    conn.close()
    return jsonify(result)


# ─── 수집 현황 요약 ──────────────────────────────────────────
@app.route("/api/summary")
def get_summary():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    stores = conn.execute("SELECT COUNT(DISTINCT store) FROM books").fetchone()[0]
    categories = conn.execute("SELECT COUNT(DISTINCT category) FROM books").fetchone()[0]
    last_crawled = conn.execute("SELECT MAX(crawled_at) FROM books").fetchone()[0]
    conn.close()
    return jsonify({
        "total_books": total,
        "stores": stores,
        "categories": categories,
        "last_crawled": last_crawled,
    })


# ─── 편집장 추천 현재 배치 ──────────────────────────────────
@app.route("/api/editorial")
def get_editorial():
    """DB에 저장된 최근 편집장 추천 도서 4권 반환."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT title, author, publisher, cover_url, editorial_text, md_info, link,
               DATE(crawled_at) AS recommended_date
        FROM editorial
        WHERE store='알라딘'
        ORDER BY crawled_at DESC
        LIMIT 4
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ─── 1단계 통계 분석 API ─────────────────────────────────────

@app.route("/api/analysis/category-dist")
def analysis_category_dist():
    """분야별 베스트셀러 분포"""
    from analysis.stats_analyzer import get_category_distribution
    return jsonify(get_category_distribution())


@app.route("/api/analysis/common-rate")
def analysis_common_rate():
    """두 서점 공통 진입률"""
    from analysis.stats_analyzer import get_common_entry_rate
    return jsonify(get_common_entry_rate())


@app.route("/api/analysis/publisher-rank")
def analysis_publisher_rank():
    """출판사별 순위 점유율 (쿼리: ?top=15&category=소설)"""
    top_n    = int(request.args.get("top", 15))
    category = request.args.get("category")
    from analysis.stats_analyzer import get_publisher_rank
    return jsonify(get_publisher_rank(top_n=top_n, category=category))


@app.route("/api/analysis/author-overlap")
def analysis_author_overlap():
    """분야별 TOP10 내 다작 저자 분석 (쿼리: ?top=10)"""
    top_n = int(request.args.get("top", 10))
    from analysis.stats_analyzer import get_author_overlap
    return jsonify(get_author_overlap(top_n=top_n))


@app.route("/api/analysis/rank-trend")
def analysis_rank_trend():
    """전체 순위 날짜별 순위 변동"""
    from analysis.stats_analyzer import get_rank_trend
    return jsonify(get_rank_trend())


@app.route("/api/analysis/rising-keywords")
def analysis_rising_keywords():
    """급등 도서 키워드 TOP N (쿼리: ?top=10)"""
    top_n = int(request.args.get("top", 10))
    from analysis.stats_analyzer import get_rising_keywords
    return jsonify(get_rising_keywords(top_n=top_n))


@app.route("/api/analysis/cross-keywords")
def analysis_cross_keywords():
    """분야 횡단 키워드 TOP N (쿼리: ?top=10&min_cat=2)"""
    top_n   = int(request.args.get("top", 10))
    min_cat = int(request.args.get("min_cat", 2))
    from analysis.stats_analyzer import get_cross_category_keywords
    return jsonify(get_cross_category_keywords(top_n=top_n, min_categories=min_cat))


@app.route("/api/analysis/entry-status")
def analysis_entry_status():
    """월별 신규 진입 / 유지 / 이탈 탐지 (쿼리: ?year=2026&month=7)"""
    from datetime import datetime
    now = datetime.now()
    year  = int(request.args.get("year",  now.year))
    month = int(request.args.get("month", now.month))
    from analysis.stats_analyzer import get_monthly_entry_status
    return jsonify(get_monthly_entry_status(year, month))


@app.route("/api/analysis/category-persistence")
def analysis_category_persistence():
    """분야별 순위 지속 기간"""
    from analysis.stats_analyzer import get_category_persistence
    return jsonify(get_category_persistence())


@app.route("/api/analysis/rising-signal-rate")
def analysis_rising_signal_rate():
    """급등/신규 도서 → 다음 수집일 TOP10 유지율"""
    from analysis.stats_analyzer import get_rising_signal_rate
    return jsonify(get_rising_signal_rate())


@app.route("/api/analysis/category-turnover")
def analysis_category_turnover():
    """분야별 TOP10 교체율 (쿼리: ?top=10)"""
    top_n = int(request.args.get("top", 10))
    from analysis.stats_analyzer import get_category_turnover_rate
    return jsonify(get_category_turnover_rate(top_n=top_n))


@app.route("/api/analysis/signal-cross")
def analysis_signal_cross():
    """분야별 교체율 × 신규 진입 유지율 교차 분석 (쿼리: ?top=10)"""
    top_n = int(request.args.get("top", 10))
    from analysis.stats_analyzer import get_category_signal_cross
    return jsonify(get_category_signal_cross(top_n=top_n))


@app.route("/api/analysis/editorial-impact")
def analysis_editorial_impact():
    """편집장 추천 → 베스트셀러 영향 분석"""
    from analysis.stats_analyzer import get_editorial_impact
    return jsonify(get_editorial_impact())


# ─── 프론트엔드 서빙 ─────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
