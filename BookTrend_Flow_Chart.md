# BookTrend 플로우차트

## 1. 전체 시스템 플로우

```mermaid
flowchart TD
    A([시스템 시작]) --> B[Flask 서버 실행\nbackend/app.py]
    B --> C[SQLite DB 초기화\nbooks · trends 테이블 생성]
    C --> D[웹 대시보드 로딩\nfrontend/index.html]
    D --> E{DB에 수집 데이터\n있음?}
    E -- 없음 --> F[빈 대시보드 표시\n'데이터 없음' 안내]
    E -- 있음 --> G[대시보드 전체 렌더링]
    F --> H([사용자 대기])
    G --> H
    H --> I{사용자 액션}
    I -- 크롤링 버튼 클릭 --> J[크롤링 플로우 시작]
    I -- 분야 탭 클릭 --> K[해당 분야 데이터 필터링 표시]
    I -- 서점 탭 클릭 --> L[알라딘/Yes24 전환 표시]
    J --> M[대시보드 자동 갱신]
    K --> H
    L --> H
    M --> H
```

---

## 2. 크롤링 플로우 (비동기 백그라운드)

```mermaid
flowchart TD
    A([크롤링 버튼 클릭]) --> B[POST /api/crawl 요청]
    B --> C{이미 크롤링\n실행 중?}
    C -- 예 --> D[토스트: '이미 크롤링 중입니다'\n버튼 유지]
    C -- 아니오 --> E[백그라운드 스레드 생성\nthreading.Thread]
    E --> F[버튼 비활성화\n'⏳ 크롤링 중...' 표시]
    E --> G[프론트엔드: 2초마다\nGET /api/crawl/status 폴링]

    subgraph BACKGROUND [백그라운드 스레드]
        H[알라딘 크롤링 시작] --> I[TTB API 7개 분야\n각 3권 수집]
        I --> J[wbest.aspx 2개 분야\n건강/취미·어린이 수집]
        J --> K[Yes24 크롤링 시작]
        K --> L{카테고리 요청}
        L --> M{응답 성공?}
        M -- 성공 --> N[HTML 파싱\n도서 정보 추출]
        M -- 실패 --> O{재시도\n횟수 < 3?}
        O -- 예 --> P[3초 대기 후 재시도]
        P --> M
        O -- 아니오 --> Q[해당 분야 빈 배열 반환]
        N --> R{다음 카테고리\n있음?}
        Q --> R
        R -- 예 --> L
        R -- 아니오 --> S[SQLite 저장\n중복 제거 후 INSERT]
        S --> T[트렌드 분석\nanalyze_trends 실행]
        T --> U[상태: '완료']
    end

    E --> H
    U --> V[폴링: 상태 '완료' 감지]
    V --> W[버튼 활성화 복구]
    W --> X[대시보드 전체 섹션 갱신]
    X --> Y([완료])
    D --> Y
```

---

## 3. 알라딘 크롤링 상세 플로우

```mermaid
flowchart TD
    A([알라딘 크롤링 시작]) --> B{TTB API 키\n.env 로드 성공?}
    B -- 실패 --> C[오류 출력: 'API 키 없음'\n.env 설정 안내]
    B -- 성공 --> D[TTB_CATEGORIES 순회\n7개 분야]

    subgraph TTB [TTB API 방식 - 7개 분야]
        D --> E[GET TTB API\nCategoryId 파라미터 전달]
        E --> F{응답 item 배열\n비어있음?}
        F -- 예 --> G[해당 분야 스킵]
        F -- 아니오 --> H[상위 3권 파싱\n제목·저자·출판사·표지URL]
        H --> I[SQLite 저장]
        I --> J[1초 대기]
        J --> K{다음 TTB\n분야 있음?}
        K -- 예 --> E
        K -- 아니오 --> L[WEB_CATEGORIES 순회\n2개 분야]
    end

    subgraph WEB [wbest.aspx 방식 - 2개 분야]
        L --> M[GET wbest.aspx\nCID 파라미터 전달]
        M --> N{a.bo3 요소\n파싱 성공?}
        N -- 실패 --> O[해당 분야 스킵]
        N -- 성공 --> P[a.bo3 = 제목 리스트\nimg.front_cover = 표지 리스트\n순서 = 순위]
        P --> Q[상위 3권 zip 매핑\n저자·출판사는 빈 문자열]
        Q --> R[SQLite 저장]
        R --> S[1초 대기]
        S --> T{다음 WEB\n분야 있음?}
        T -- 예 --> M
        T -- 아니오 --> U([알라딘 크롤링 완료])
    end

    C --> U
    G --> K
    O --> T
```

---

## 4. Yes24 크롤링 상세 플로우

```mermaid
flowchart TD
    A([Yes24 크롤링 시작]) --> B[CATEGORIES 9개 분야 순회]
    B --> C[_make_url 호출\ncategoryNumber + 현재연도 적용]
    C --> D[GET weekbestseller\ntimeout=20s]
    D --> E{HTTP 응답\n성공?}
    E -- 성공 --> F[BeautifulSoup HTML 파싱]
    E -- 실패 --> G{시도 횟수\n< 3?}
    G -- 예 --> H[3초 대기]
    H --> D
    G -- 아니오 --> I[빈 배열 반환]

    F --> J[.itemUnit 목록 추출]
    J --> K{itemUnit\n비어있음?}
    K -- 예 --> I
    K -- 아니오 --> L[각 itemUnit에서 파싱\nem.ico.rank = 순위\na.gd_name = 제목\n.info_auth = 저자\ndata-original = 표지URL]
    L --> M[상위 3권 필터]
    M --> N{표지 URL\ndata-original 존재?}
    N -- 예 --> O[URL 내 /L → /XL 변환]
    N -- 아니오 --> P[상품 페이지에서 goods_id 추출\nhttps://image.yes24.com/goods/{id}/XL]
    O --> Q[SQLite 저장]
    P --> Q
    Q --> R{다음 분야\n있음?}
    R -- 예 --> B
    R -- 아니오 --> S([Yes24 크롤링 완료])
    I --> R
```

---

## 5. NLP 트렌드 분석 플로우

```mermaid
flowchart TD
    A([트렌드 분석 시작]) --> B[kiwipiepy Kiwi 인스턴스 로드\n싱글턴 패턴]
    B --> C[DB에서 분야 목록 조회\nSELECT DISTINCT category]
    C --> D[분야 순회]
    D --> E[해당 분야 도서 제목 전체 조회]
    E --> F[제목 순회]
    F --> G[kiwi.tokenize 형태소 분석]
    G --> H{명사 태그\nNN* 해당?}
    H -- 아니오 --> I[다음 토큰]
    H -- 예 --> J{길이 >= 2\n숫자 아님?}
    J -- 아니오 --> I
    J -- 예 --> K{불용어\n포함?}
    K -- 예 --> I
    K -- 아니오 --> L[대표 키워드 확정\n해당 책의 첫 번째 유효 명사]
    L --> M[all_nouns에 추가\n1책 = 1키워드]
    M --> N{다음 제목\n있음?}
    I --> O{해당 책 키워드\n이미 확정?}
    O -- 예 --> N
    O -- 아니오 --> I
    N -- 예 --> F
    N -- 아니오 --> P[Counter 빈도 계산]
    P --> Q[상위 10개 키워드 추출]
    Q --> R[trends 테이블 기존 데이터 삭제\nDELETE WHERE category=?]
    R --> S[trends 테이블 INSERT]
    S --> T{다음 분야\n있음?}
    T -- 예 --> D
    T -- 아니오 --> U([트렌드 분석 완료\n9개 분야 저장])
```

---

## 6. 대시보드 렌더링 플로우

```mermaid
flowchart TD
    A([페이지 로드]) --> B[API_BASE = http://localhost:5000]
    B --> C[병렬 데이터 요청]

    C --> D[GET /api/books]
    C --> E[GET /api/trends]
    C --> F[GET /api/compare]

    D --> G[베스트셀러 카드 렌더링\n분야별 · 서점별 그룹핑]
    E --> H[분야 선택 드롭다운 생성]
    H --> I[Chart.js 막대 차트 렌더링\n선택 분야 키워드 Top 10]
    F --> J[서점별 비교 패널 렌더링]
    J --> K{common: true\n공통 도서?}
    K -- 예 --> L[초록 하이라이트\n'공통' 배지 표시]
    K -- 아니오 --> M[일반 스타일 표시]

    G --> N[렌더링 완료]
    I --> N
    L --> N
    M --> N
    N --> O([대시보드 표시])
```
