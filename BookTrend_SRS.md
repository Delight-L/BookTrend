# 소프트웨어 요구사항 명세서 (SRS)
## BookTrend — 도서 베스트셀러 트렌드 대시보드

---

## 1. 서론 (Introduction)

### 1.1 목적 (Purpose)

본 문서는 **BookTrend** 시스템 개발을 위한 요구사항을 정의한다.  
알라딘·Yes24 두 서점의 분야별 베스트셀러를 자동 수집하고, 키워드 트렌드를 분석하여 웹 대시보드로 시각화하는 서비스의 설계·구현·테스트 단계에서 개발자와 이해관계자가 참조한다.

### 1.2 범위 (Scope)

- **사용자**: 도서 트렌드에 관심 있는 개인 사용자 (독자, 출판 관계자, 콘텐츠 기획자)
- **기능**: 베스트셀러 크롤링, SQLite 저장, 한국어 NLP 키워드 분석, 웹 대시보드 시각화, 서점 간 순위 비교
- **목표**: 두 서점 베스트셀러를 한 화면에서 비교하고 분야별 도서 트렌드를 파악하는 시간을 단축

### 1.3 정의 및 약어 (Definitions, Acronyms, Abbreviations)

| 약어 | 정의 |
|------|------|
| TTB API | 알라딘 오픈 API (Thing's The Best) |
| NLP | Natural Language Processing (자연어 처리) |
| SRS | Software Requirements Specification |
| CID | Category ID (알라딘 카테고리 식별자) |
| wbest | 알라딘 웹 베스트셀러 페이지 (wbest.aspx) |
| weekbestseller | Yes24 주간 베스트셀러 엔드포인트 |
| SQLite | 파일 기반 경량 관계형 데이터베이스 |

### 1.4 참조 문서 (References)

- 알라딘 TTB Open API 문서: `http://www.aladin.co.kr/ttb/api/ItemList.aspx`
- Yes24 주간 베스트셀러 엔드포인트: `https://www.yes24.com/product/category/weekbestseller`
- IEEE 830-1998: Software Requirements Specification 표준
- kiwipiepy 한국어 형태소 분석기 공식 문서

---

## 2. 전체 설명 (Overall Description)

### 2.1 제품 관점 (Product Perspective)

본 시스템은 로컬 환경에서 단독으로 동작하는 경량 웹 서비스이다.  
크롤러가 외부 서점 API와 웹 페이지에서 데이터를 수집하고, 분석 엔진이 한국어 NLP로 키워드를 추출한 후, Flask 웹 서버가 대시보드를 제공한다.

**아키텍처 개요:**

```
[알라딘 TTB API / wbest.aspx]  [Yes24 weekbestseller]
              ↓                            ↓
       [Crawler Layer (Python requests + BeautifulSoup)]
                         ↓
               [SQLite DB (books, trends)]
                         ↓
        [NLP 분석 엔진 (kiwipiepy 형태소 분석)]
                         ↓
         [Flask REST API (백엔드, /api/*)]
                         ↓
     [웹 대시보드 (HTML + Vanilla JS + Chart.js)]
```

### 2.2 제품 기능 요약 (Product Functions)

- 분야별(9개) 베스트셀러 상위 3권을 두 서점에서 자동 수집
- 수집 데이터를 SQLite에 날짜 기준으로 저장 (중복 방지)
- 한국어 NLP로 도서 제목에서 대표 키워드 1개/책 추출 후 분야별 빈도 분석
- 웹 대시보드에서 순위, 키워드 트렌드, 서점 간 순위 비교 시각화
- 크롤링 버튼(비동기 백그라운드 실행) + 진행 상태 폴링

### 2.3 사용자 특성 (User Characteristics)

- **일반 사용자**: IT 지식 낮음, 브라우저로 대시보드 열람만 수행
- **운영자(본인)**: Python 환경 설정, `.env` API 키 관리, Flask 서버 실행 담당

### 2.4 제약 조건 (Constraints)

- 운영 환경: Windows 10/11 로컬 (Python 3.10+, venv)
- 데이터베이스: SQLite (별도 DB 서버 없음)
- 알라딘 API 키: `.env` 파일에만 저장 — 코드·버전 관리에 절대 하드코딩·커밋 금지
- Yes24 크롤링: 공개 웹 페이지 HTML 파싱 (API 없음) — 사이트 구조 변경 시 셀렉터 수정 필요
- 분야 수: 9개 고정 (경제/경영, 자기계발, 소설, 인문, 사회과학, 과학, 컴퓨터/IT, 건강/취미, 어린이)
- 수집 권수: 분야당 상위 3권

### 2.5 가정 및 의존성 (Assumptions and Dependencies)

- 알라딘 TTB API 서비스가 정상 운영 중임을 가정
- Yes24 weekbestseller 페이지 HTML 구조(셀렉터: `.itemUnit`, `a.gd_name`, `em.ico.rank`)가 유지됨을 가정
- 알라딘 wbest.aspx 페이지 구조(`a.bo3`, `img.front_cover`)가 유지됨을 가정
- 로컬 인터넷 연결이 안정적일 것을 가정
- Python 패키지: `requests`, `beautifulsoup4`, `flask`, `kiwipiepy`, `python-dotenv`

---

## 3. 기능 요구사항 (Functional Requirements)

| ID | 요구사항 설명 | 우선순위 | 비고 |
|----|--------------|----------|------|
| FR-01 | 시스템은 알라딘 TTB API로 7개 분야(경제/경영·자기계발·소설·인문·사회과학·과학·컴퓨터IT) 베스트셀러를 수집해야 한다. | Must | CategoryId 기준, 분야당 3권 |
| FR-02 | 시스템은 알라딘 wbest.aspx 웹 페이지에서 건강/취미(CID=55890)·어린이(CID=1108) 베스트셀러를 수집해야 한다. | Must | TTB API가 해당 CID 미지원 |
| FR-03 | 시스템은 Yes24 weekbestseller 엔드포인트에서 9개 분야 베스트셀러를 수집해야 한다. | Must | 연도 파라미터 자동 적용 |
| FR-04 | 수집된 도서 데이터(서점·분야·순위·제목·저자·출판사·표지URL)를 SQLite에 저장해야 한다. | Must | 당일 동일 조합 중복 저장 방지 |
| FR-05 | 알라딘 API 키는 `.env` 파일에서만 로드하며, 소스코드 및 버전 관리에 노출되어서는 안 된다. | Must | `.gitignore`에 `.env` 등록 |
| FR-06 | 크롤링 요청 시 백그라운드 스레드에서 실행되어야 하며, 진행 상태를 `/api/crawl/status`로 폴링할 수 있어야 한다. | Must | 동기 실행 시 브라우저 타임아웃 발생 |
| FR-07 | Yes24 각 카테고리 요청이 실패할 경우 3회까지 재시도(retry)해야 한다. | Must | 시도 간 3초 대기 |
| FR-08 | 수집된 도서 제목에서 한국어 형태소 분석(kiwipiepy)으로 명사를 추출하되, 책 한 권당 대표 키워드 1개만 사용해야 한다. | Must | 불용어 제외 후 첫 번째 유효 명사 |
| FR-09 | 분야별 키워드 빈도 Top 10을 산출하여 `trends` 테이블에 저장해야 한다. | Must | 크롤링 완료 직후 자동 실행 |
| FR-10 | 웹 대시보드는 분야별 베스트셀러 순위를 표지 이미지·제목·저자와 함께 표시해야 한다. | Must | 알라딘/Yes24 탭 구분 |
| FR-11 | 웹 대시보드는 분야별 키워드 빈도를 막대 차트(Chart.js)로 표시해야 한다. | Must | 상위 10개 키워드 |
| FR-12 | 웹 대시보드는 분야별로 알라딘·Yes24 순위를 나란히 비교하고, 두 서점 공통 도서에 "공통" 배지를 표시해야 한다. | Must | `/api/compare` 엔드포인트 |
| FR-13 | 크롤링 버튼 클릭 후 완료 시 대시보드 전체 섹션이 자동 갱신되어야 한다. | Should | 폴링 완료 후 reload |

---

## 4. 비기능 요구사항 (Non-functional Requirements)

| ID | 요구사항 설명 | 기준치 | 비고 |
|----|--------------|--------|------|
| NFR-01 | 전체 크롤링(알라딘 + Yes24 9개 분야) 완료 시간 | 60초 이내 | 네트워크 정상 시 |
| NFR-02 | Yes24 단일 카테고리 요청 타임아웃 | 20초 | 재시도 포함 최대 69초/분야 |
| NFR-03 | 대시보드 초기 로딩 응답 시간 | 2초 이내 | 로컬 SQLite 조회 기준 |
| NFR-04 | API 키 보안 | 소스코드 내 하드코딩 0건 | CI/CD 도입 시 secret scan 적용 |
| NFR-05 | 동시 크롤링 실행 제한 | 중복 실행 1회 방지 | 실행 중 재요청 시 상태 반환 |
| NFR-06 | 유지보수성 — 카테고리 코드 변경 | 단일 파일(CATEGORIES dict)만 수정 | aladin.py, yes24.py 각각 |
| NFR-07 | 코드 내 API 키 노출 금지 | .env 미적용 시 크롤링 차단 | 환경변수 미설정 시 명확한 오류 출력 |

---

## 5. 외부 인터페이스 요구사항

### 5.1 사용자 인터페이스 (UI/UX)

- **단일 페이지 웹 대시보드** (SPA, `index.html`)
- 우상단 "🔄 지금 크롤링" 버튼 → 클릭 시 비활성화 + 진행 메시지 표시 → 완료 시 자동 복구
- 섹션 구성: 베스트셀러 순위 카드 / 키워드 빈도 막대 차트 / 서점별 순위 비교 패널
- 두 서점 공통 도서: 초록색 하이라이트 + "공통" 배지
- 토스트 알림으로 크롤링 상태 메시지 표시

### 5.2 하드웨어 인터페이스

- 클라이언트: PC 브라우저 (Chrome, Edge 최신 버전 권장)
- 서버: 로컬 PC (Windows 10/11, 2GB RAM 이상)

### 5.3 소프트웨어 인터페이스

**REST API 엔드포인트 (Flask, 기본 포트 5000)**

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/books` | GET | 전체 도서 목록 (서점·분야·순위 포함) |
| `/api/categories` | GET | 분야 목록 |
| `/api/trends` | GET | 분야별 키워드 빈도 목록 |
| `/api/compare` | GET | 서점별 순위 비교 + 공통 도서 여부 |
| `/api/common` | GET | 두 서점 공통 베스트셀러 |
| `/api/summary` | GET | 분야별 요약 통계 |
| `/api/crawl` | POST | 크롤링 시작 (백그라운드 실행) |
| `/api/crawl/status` | GET | 크롤링 진행 상태 조회 |

**데이터베이스 스키마 (SQLite)**

```sql
-- 도서 테이블
CREATE TABLE books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    store       TEXT NOT NULL,       -- '알라딘' | '예스24'
    category    TEXT NOT NULL,       -- 분야명
    rank        INTEGER NOT NULL,    -- 1~3
    title       TEXT NOT NULL,
    author      TEXT,
    publisher   TEXT,
    cover_url   TEXT,
    crawled_at  TEXT NOT NULL        -- ISO 8601 datetime
);

-- 키워드 트렌드 테이블
CREATE TABLE trends (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    keyword     TEXT NOT NULL,
    frequency   INTEGER NOT NULL,
    crawled_at  TEXT NOT NULL
);
```

### 5.4 외부 API 인터페이스

**알라딘 TTB API**
- URL: `http://www.aladin.co.kr/ttb/api/ItemList.aspx`
- 인증: Query Parameter `ttbkey` (`.env`에서 로드)
- 응답: JSON (`item[]` 배열)

**Yes24 weekbestseller**
- URL: `https://www.yes24.com/product/category/weekbestseller`
- 인증: 없음 (공개 웹 페이지)
- 파싱: BeautifulSoup (`.itemUnit`, `a.gd_name`, `em.ico.rank`, `.info_auth`)

**알라딘 wbest.aspx (건강/취미·어린이 전용)**
- URL: `https://www.aladin.co.kr/shop/common/wbest.aspx`
- 파싱: BeautifulSoup (`a.bo3` = 제목, `img.front_cover` = 표지)

### 5.5 통신 인터페이스

- 프로토콜: HTTP (로컬 개발 환경, 포트 5000)
- 외부 API 통신: HTTPS
- 크롤링 폴링 간격: 2초

---

## 6. 시스템 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                    외부 데이터 소스                          │
│  [알라딘 TTB API]  [알라딘 wbest.aspx]  [Yes24 weekbest]   │
└──────────────┬─────────────────┬──────────────┬─────────────┘
               ↓                 ↓              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Crawler Layer (Python)                     │
│   crawler/aladin.py          crawler/yes24.py               │
│  - TTB API (7개 분야)         - weekbestseller (9개 분야)   │
│  - wbest.aspx (2개 분야)      - 재시도 로직 (3회, 20s)      │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              Database Layer (SQLite)                         │
│   db/database.py  ·  books 테이블  ·  trends 테이블         │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│           NLP Analysis Layer (kiwipiepy)                     │
│   analysis/trend_analyzer.py                                 │
│   - 책당 대표 키워드 1개 추출 → 분야별 빈도 계산            │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│               Backend API (Flask)                            │
│   backend/app.py  ·  /api/* 엔드포인트                      │
│   - 백그라운드 스레드 크롤링 + 상태 폴링                    │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│            Frontend Dashboard (HTML/JS)                      │
│   frontend/index.html  ·  Chart.js                          │
│   - 순위 카드 / 키워드 차트 / 서점 비교 패널               │
└─────────────────────────────────────────────────────────────┘
```

**디렉토리 구조**

```
BookTrend/
├── .env                  # API 키 (버전 관리 제외)
├── .gitignore            # .env, __pycache__, venv/, db/*.db
├── backend/
│   └── app.py            # Flask 앱 + REST API
├── crawler/
│   ├── aladin.py         # 알라딘 크롤러 (TTB API + wbest.aspx)
│   └── yes24.py          # Yes24 크롤러 (weekbestseller)
├── analysis/
│   └── trend_analyzer.py # 키워드 NLP 분석
├── db/
│   └── database.py       # SQLite 연결 및 스키마 초기화
├── frontend/
│   └── index.html        # 단일 페이지 대시보드
└── reset_and_crawl.py    # DB 초기화 + 전체 크롤링 실행
```

---

## 7. 요구사항 추적성 매트릭스 (RTM)

| 요구사항 ID | 테스트 케이스 ID | 설명 |
|------------|----------------|------|
| FR-01 | TC-01 | 알라딘 TTB API 7개 분야 각 3권 수집 성공 검증 |
| FR-02 | TC-02 | wbest.aspx 건강/취미·어린이 제목·표지 정상 파싱 확인 |
| FR-03 | TC-03 | Yes24 9개 분야 weekbestseller 수집 결과와 실제 사이트 비교 |
| FR-04 | TC-04 | 동일 날짜 중복 실행 시 DB 레코드 중복 없음 확인 |
| FR-05 | TC-05 | `.env` 미적용 상태에서 크롤링 시 오류 메시지 출력 확인 |
| FR-06 | TC-06 | 크롤링 버튼 클릭 후 `/api/crawl/status` 폴링으로 완료 감지 확인 |
| FR-07 | TC-07 | Yes24 타임아웃 발생 시 3회 재시도 후 빈 배열 반환 확인 |
| FR-08 | TC-08 | 동일 제목에서 키워드가 1개만 카운트되는지 단위 테스트 |
| FR-09 | TC-09 | 분야별 trends 테이블에 Top 10 키워드 저장 여부 확인 |
| FR-10 | TC-10 | 대시보드 베스트셀러 카드에 표지·제목·저자 표시 확인 |
| FR-11 | TC-11 | 키워드 막대 차트 렌더링 및 데이터 정확성 확인 |
| FR-12 | TC-12 | 공통 도서에 "공통" 배지 표시 및 초록 하이라이트 확인 |
| FR-13 | TC-13 | 크롤링 완료 후 대시보드 자동 갱신 확인 |
| NFR-01 | TC-14 | 전체 크롤링 60초 이내 완료 시간 측정 |
| NFR-04 | TC-15 | 소스코드 전체에서 API 키 하드코딩 0건 grep 확인 |
| NFR-05 | TC-16 | 크롤링 중 중복 POST 요청 시 "이미 실행 중" 응답 확인 |

---

## 8. 부록 (Appendices)

### 8.1 용어집

| 용어 | 설명 |
|------|------|
| TTB API | 알라딘에서 제공하는 도서 정보 오픈 API. `ttbkey` 인증 필요 |
| weekbestseller | Yes24의 주간 베스트셀러 전용 엔드포인트. `saleYear`, `type=week` 파라미터 사용 |
| wbest.aspx | 알라딘 웹 베스트셀러 페이지. 일부 카테고리는 TTB API 미지원으로 이 페이지를 직접 파싱 |
| CategoryId (CID) | 알라딘 카테고리 식별자. TTB API용 CID와 웹 페이지용 CID가 다를 수 있음 |
| kiwipiepy | 카카오에서 공개한 한국어 형태소 분석 라이브러리 |
| 불용어 (Stopword) | 트렌드 분석 시 제외하는 의미 없는 단어 목록 ("것", "수", "등" 등) |
| 대표 키워드 | 책 한 권의 제목에서 불용어를 제외한 첫 번째 유효 명사 (책당 1개) |

### 8.2 카테고리 코드 매핑

**알라딘 TTB API CategoryId**

| 분야 | CategoryId |
|------|-----------|
| 경제/경영 | 170 |
| 자기계발 | 336 |
| 소설 | 1 |
| 인문 | 656 |
| 사회과학 | 798 |
| 과학 | 987 |
| 컴퓨터/IT | 351 |

**알라딘 wbest.aspx CID (웹 직접 크롤링)**

| 분야 | CID |
|------|-----|
| 건강/취미 | 55890 |
| 어린이 | 1108 |

**Yes24 weekbestseller categoryNumber**

| 분야 | categoryNumber |
|------|---------------|
| 경제/경영 | 001001025 |
| 자기계발 | 001001026 |
| 소설 | 001001046 |
| 인문 | 001001019 |
| 사회과학 | 001001022 |
| 과학 | 001001002 |
| 컴퓨터/IT | 001001003 |
| 건강/취미 | 001001011 |
| 어린이 | 001001016 |

### 8.3 환경 설정

```bash
# 필수 패키지 설치
pip install requests beautifulsoup4 flask kiwipiepy python-dotenv

# .env 파일 생성 (절대 커밋 금지)
echo "ALADIN_TTB_KEY=발급받은키" > .env

# 서버 실행
python backend/app.py
```

### 8.4 알려진 제약사항

- 알라딘 건강/취미·어린이 분야는 wbest.aspx 파싱 방식 특성상 **저자·출판사 정보가 수집되지 않음**
- Yes24 크롤링은 공개 HTML 파싱에 의존하므로 사이트 UI 개편 시 셀렉터 수정 필요
- 알라딘 TTB API는 하루 요청 횟수 제한이 있을 수 있음 (알라딘 API 정책 확인 필요)
