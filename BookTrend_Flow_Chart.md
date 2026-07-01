# BookTrend 시스템 플로우차트

```mermaid
flowchart TD
    %% ── 스타일 정의 ──────────────────────────────────────────
    classDef user     fill:#4a90d9,stroke:#2c6fad,color:#fff,rx:8
    classDef flask    fill:#3d6b5e,stroke:#2d5b4e,color:#fff
    classDef crawler  fill:#ffffff,stroke:#3d6b5e,color:#3d6b5e,stroke-width:2px
    classDef source   fill:#3d6b5e,stroke:#2d5b4e,color:#fff
    classDef db       fill:#f4b07a,stroke:#d4946a,color:#6b3a10
    classDef nlp      fill:#ffffff,stroke:#3d6b5e,color:#3d6b5e,stroke-width:2px
    classDef dash     fill:#e3f2fd,stroke:#1565c0,color:#1565c0
    classDef decision fill:#fff9c4,stroke:#f9a825,color:#5d4037

    %% ── 사용자 액션 ──────────────────────────────────────────
    U([👤 사용자]):::user
    BTN["📡 트렌드 스캔 버튼 클릭"]:::user

    U --> BTN
    BTN -->|"POST /api/crawl"| BE

    %% ── Flask 백엔드 ─────────────────────────────────────────
    BE["⚙️ Flask 백엔드\napp.py"]:::flask

    BE --> RUNNING{"이미 크롤링 중?"}:::decision
    RUNNING -->|"Yes"| SKIP["⚠️ 이미 실행 중 메시지 반환"]:::dash
    RUNNING -->|"No"| THREAD["🔄 백그라운드 스레드 시작\nthreading.Thread"]:::flask

    %% ── 크롤링 단계 (순차 실행) ─────────────────────────────
    THREAD --> C1

    subgraph CRAWL["📦 크롤링 파이프라인 (순차 실행)"]
        direction TB

        subgraph C1["① 분야별 베스트셀러 크롤러 — aladin.py / yes24.py"]
            direction LR
            A1["알라딘 TTB API\n9개 분야"]:::source
            A2["알라딘 wbest.aspx\n건강/취미, 어린이"]:::source
            Y1["Yes24 weekbestseller\n10개 분야"]:::source
            Y2["Yes24 bestseller\n여행 종합"]:::source
        end

        subgraph C2["② 전체 판매순위 크롤러 — overall.py"]
            direction LR
            A3["알라딘 전체순위\nwbest.aspx"]:::source
            Y3["Yes24 전체 베스트셀러\nbestseller"]:::source
        end

        subgraph C3["③ 편집장 추천 크롤러 — editorial.py"]
            direction LR
            A4["알라딘 편집장 추천\nweeklyeditorialmeeting"]:::source
            Y4["Yes24 오늘의 책\nevent.yes24.com/todayBook"]:::source
        end
    end

    %% ── 데이터 저장 ──────────────────────────────────────────
    C1 --> SAVE
    C2 --> SAVE
    SAVE["💾 데이터 저장\ndatabase.py\nINSERT INTO books"]:::crawler
    SAVE --> BOOKSDB[("SQLite\nbooks DB")]:::db

    C3 -->|"in-memory cache\n_editorial_cache"| BE_CACHE["📋 Flask 메모리 캐시\n_editorial_cache"]:::flask

    %% ── NLP 분석 ─────────────────────────────────────────────
    BOOKSDB --> NLP["🔬 NLP 분석\ntrend_analyzer.py\nkiwipiepy 형태소 분석"]:::nlp
    NLP --> TRENDSDB[("SQLite\ntrends DB")]:::db

    %% ── Flask API 응답 ───────────────────────────────────────
    BOOKSDB --> API
    TRENDSDB --> API
    BE_CACHE --> API

    subgraph API["🌐 Flask REST API 엔드포인트"]
        direction TB
        EP1["/api/overall\n전체 판매 순위"]:::flask
        EP2["/api/compare\n서점별 순위 비교"]:::flask
        EP3["/api/trends\n키워드 트렌드"]:::flask
        EP4["/api/editorial\n편집장 추천 오늘의 책"]:::flask
        EP5["/api/books\n분야별 베스트셀러"]:::flask
        EP6["/api/common\n공통 베스트셀러"]:::flask
    end

    %% ── 프론트엔드 대시보드 ──────────────────────────────────
    API --> FE

    subgraph FE["🖥️ 프론트엔드 대시보드 — index.html"]
        direction TB
        D1["📊 전체 판매 순위\n알라딘 / Yes24 TOP10"]:::dash
        D2["🔀 서점별 순위 비교\n공통 도서 초록색 표시"]:::dash
        D3["📈 키워드 트렌드 차트\n분야별 인기 키워드"]:::dash
        D4["✍️ 편집장 추천 오늘의 책\n알라딘 & Yes24 MD 코멘트"]:::dash
    end

    FE --> U2([👤 사용자]):::user
```

---

## 시스템 구성 요약

| 구분 | 파일 | 역할 |
|------|------|------|
| **백엔드** | `backend/app.py` | Flask 서버, REST API, 크롤링 스케줄 |
| **분야 크롤러** | `crawler/aladin.py` | 알라딘 TTB API + wbest.aspx (11개 분야) |
| **분야 크롤러** | `crawler/yes24.py` | Yes24 weekbestseller + bestseller (11개 분야) |
| **전체순위 크롤러** | `crawler/overall.py` | 알라딘·Yes24 전체 판매 TOP 순위 |
| **편집장 크롤러** | `crawler/editorial.py` | 알라딘 편집장 추천 + Yes24 오늘의 책 |
| **NLP 분석** | `analysis/trend_analyzer.py` | kiwipiepy 형태소 분석 → 키워드 빈도 추출 |
| **DB 초기화** | `db/database.py` | SQLite 테이블 생성, 커넥션 관리 |
| **프론트엔드** | `frontend/index.html` | 단일 HTML 대시보드 (Vanilla JS) |

## 데이터 흐름 요약

```
외부 웹사이트 → 크롤러 (requests + BeautifulSoup)
    → SQLite books DB (최신 크롤링 날짜만 표시)
    → NLP 분석 (kiwipiepy)
    → SQLite trends DB

편집장 페이지 → 편집장 크롤러 → Flask 메모리 캐시 (_editorial_cache)

SQLite books DB  ┐
SQLite trends DB ┼→ Flask REST API → 프론트엔드 대시보드
Flask 메모리 캐시┘
```

## 주요 설계 결정 사항

- **최신 날짜 필터링**: 크롤링 시마다 기존 데이터를 삭제하지 않고 보존.  
  `WHERE DATE(crawled_at) = (SELECT MAX(DATE(crawled_at)) FROM books)` 조건으로 항상 최신 데이터만 표시.

- **편집장 추천 in-memory 저장**: DB 저장 없이 Flask 프로세스 메모리에 캐싱.  
  서버 재시작 시 자동으로 재크롤링.

- **Yes24 여행 분야 예외 처리**: `BESTSELLER_URL_OVERRIDES` 딕셔너리로  
  여행만 weekbestseller 대신 종합 bestseller 엔드포인트 사용.

- **백그라운드 크롤링**: `threading.Thread(daemon=True)` 로 논블로킹 실행.  
  `/api/crawl/status` 폴링으로 프론트엔드에서 진행 상황 표시.
