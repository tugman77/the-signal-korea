# 202 더 시그널 코리아 — CLAUDE.md (v2)

## 개요
글로벌 기술·산업 패권 뉴스를 분석해 "한국 산업은 앞으로 무엇으로 먹고 살 것인가?"에 답하는 인텔리전스 미디어.
**5단계 고정 프레임**: Fact → Meaning → Winner → Loser → Action

- **GitHub 저장소:** `tugman77/the-signal-korea` (생성 필요)
- **배포 방식:** GitHub Pages (main 브랜치 / root 디렉터리)
- **AI 모델:** `claude-sonnet-4-6`
- **DB:** 없음 (JSON 파일 기반)
- **스케줄:** 매일 KST 09:00 (`0 0 * * *` UTC)

---

## 에이전트 정체성 (Persona)

- **역할**: 대한민국 최고 경제·산업 인텔리전스 기관의 수석 산업분석가 + 20년 경력 시니어 테크 저널리스트
- **핵심 미션**: 글로벌 기술·산업 뉴스를 분석하여 "한국 산업은 앞으로 무엇으로 먹고 살 것인가?"에 답한다
- **타깃 독자**: 개인 투자자 — "이 뉴스가 내 계좌에 무슨 의미인가"에 답하는 글
- **핵심 차별화**: 대표님의 실제 소재 조달 현장 경험 ("실제 조달 현장에서는~" 한 문단 필수 삽입)

---

## 파일 구조

```
202 The Signal Korea/
├── CLAUDE.md               ← 이 파일
├── 기사자동생성.py          ← 메인 스크립트 v2 (RSS → Claude API → JSON)
├── 기사검수.py             ← 품질 검수 스크립트 (신규)
├── articles.json           ← 최신 기사 데이터 (index.html이 읽음)
├── index.html              ← 메인 뉴스 페이지 (소재타임즈 구조 업그레이드)
├── article.html            ← 기사 본문 (5단계 프레임 시각화)
├── category.html           ← 카테고리별 기사 목록 (신규)
├── search.html             ← 검색 결과 페이지 (신규)
├── about.html              ← 소개 페이지 (신규)
├── advertising.html        ← 광고문의 (신규)
├── privacy.html            ← 개인정보처리방침 (신규)
├── terms.html              ← 이용약관 (신규)
├── images/                 ← 기사 이미지 (날짜 포함: YYYY-MM-DD_article_N.jpg)
├── archive/                ← 날짜별 기사 아카이브
│   ├── index.json          ← 날짜 목록 (최대 90일)
│   └── YYYY-MM-DD.json     ← 날짜별 기사 데이터
├── scripts/
│   └── review.log          ← 기사검수 로그
└── .github/workflows/
    └── 자동기사생성.yml     ← GitHub Actions (매일 UTC 00:00 = KST 09:00)
```

---

## 컨셉 & 전략

### 간판 카테고리 비중
| 카테고리   | 비중 | 핵심 키워드                                |
|-----------|------|-------------------------------------------|
| 공급망전쟁 | 50% | 갈륨·탄탈럼·희토류·리튬 수출 규제, 소재 조달 |
| 기술패권   | 20% | 미·중 반도체 전쟁, AI 인프라, 칩 법안        |
| 산업전략   | 20% | 한국 소부장, 대기업 사업 전환, 정책·투자      |
| 글로벌분석 | 10% | 미국·EU·일본·인도 산업 동향                  |

### SEO 전략
초기에는 구체적인 소재·종목 키워드로 진입: "갈륨 수출 규제 관련주", "탄탈럼 가격 전망", "희토류 대체 공급망" 등

### 현장 경험 차별화
- action 배열 마지막 단락은 반드시 `"실제 조달 현장에서는 —"` 으로 시작
- 20년 소재 조달 영업 현장 경험을 녹인 실전 인사이트 제공

---

## 기사 포맷 이원화

### 주력 분석글 (주 3회, is_brief=false)
FACT → MEANING → WINNER → LOSER → ACTION 5단계 전체

### 속보성 글 (주 2회, is_brief=true)
FACT + ACTION 2단계만 (meaning/winner/loser는 빈 배열 `[]`)

---

## 기사 작성 핵심 규칙

### 금지 사항
- `비약적인 성장`, `주목받고 있다`, `큰 영향을 미칠 것` 같은 모호한 형용사/부사 절대 금지
- 수치 근거 없는 주장 배제

### 필수 사항
- 모든 주장에 **정량 수치**(시장 점유율%, 투자 규모, 연도, 법안명) 반드시 포함
- 각 단계 **최소 2개 이상** 구체적 통계 수치 또는 기업명 포함
- 기사 작성 전 **RSS 수집** 선행
- 최근 3일 기사 제목 → 중복 주제 방지
- action 마지막 단락: `"실제 조달 현장에서는 —"` 패턴 필수

---

## 5단계 인텔리전스 프레임

```
① FACT    (사실)   — 사건 주체·날짜·수치·공급망 명칭 포함 핵심 사실
② MEANING (의미)   — 미·중 패권 경쟁, 공급망 도미노, 기술 패러다임 전환 맥락 분석
③ WINNER  (승자)   — 반사이익 국가·산업·기업 + 정량 근거
④ LOSER   (패자)   — 타격 플레이어 + 실질 위기 요인 수치 근거
⑤ ACTION  (준비)   — 한국 산업·대기업·소부장이 지금 실행할 구체적 전략
                    (마지막 단락: "실제 조달 현장에서는 —" 필수)
```

각 단계는 `articles.json`에 별도 배열 필드로 저장 (`fact`, `meaning`, `winner`, `loser`, `action`).

---

## 기사 데이터 포맷

```json
{
  "id": 0,
  "category": "공급망전쟁",
  "tag_type": "tag-supply",
  "title": "중국 갈륨 수출 99% 차단, 한국 연간 700억 리스크",
  "summary": "...",
  "is_brief": false,
  "fact":    ["단락1", "단락2", "단락3"],
  "meaning": ["단락1", "단락2"],
  "winner":  ["단락1", "단락2"],
  "loser":   ["단락1", "단락2"],
  "action":  ["단락1", "단락2", "실제 조달 현장에서는 — ..."],
  "image_keyword": "gallium export restriction Korea semiconductor",
  "image_url": "images/2026-07-03_article_0.jpg",
  "is_featured": true,
  "timestamp": "오전 09:00"
}
```

### 카테고리 & 태그 타입
| 카테고리   | tag_type       | 색상          |
|-----------|---------------|--------------|
| 기술패권   | tag-hegemony  | 빨강 (#b91c1c) |
| 공급망전쟁 | tag-supply    | 앰버 (#b45309) |
| 산업전략   | tag-strategy  | 초록 (#15803d) |
| 글로벌분석 | tag-global    | 파랑 (#1d4ed8) |

---

## 디자인 테마

- **배경:** 어두운 네이비(`#0a0f1e`) 헤더, 골드 어센트(`#e8a000`)
- **로고:** THE **SIGNAL** KOREA (SIGNAL은 골드 강조)
- **5단계 섹션 색상:**
  - FACT: 딥 블루 (`#1e3a5f`)
  - MEANING: 인디고 (`#1e1b4b`)
  - WINNER: 다크 그린 (`#14532d`)
  - LOSER: 다크 레드 (`#450a0a`)
  - ACTION: 다크 골드 (`#1c1300` + 골드 테두리) — 가장 강조

---

## 이미지 우선순위 (기사자동생성.py v2)

1. **Unsplash API** (UNSPLASH_ACCESS_KEY 환경변수 필요)
2. **Pexels API** (PEXELS_API_KEY 환경변수 필요)
3. **Pixabay API** (PIXABAY_API_KEY 환경변수 필요)
4. **큐레이션 풀** (카테고리별 고정 Unsplash URL)
5. **picsum** (최후 수단)

이미지 파일명: `images/YYYY-MM-DD_article_N.jpg`

---

## RSS 피드

| 소스 | 키워드 |
|------|--------|
| Google뉴스(한국어) | 갈륨 게르마늄 수출 규제 한국 공급망 |
| Google뉴스(한국어) | 미중 반도체 패권 공급망 |
| Google뉴스(한국어) | AI 반도체 한국 산업전략 |
| Google뉴스(영어) | supply chain semiconductor Korea strategy |
| Google뉴스(영어) | tech war US China chip Korea |
| 연합뉴스 | 경제 |
| 전자신문 | 전체 |

---

## index.html 업그레이드 내역 (소재타임즈 구조)

- `heroIndices Set` — 히어로 기사 중복 방지
- `seenTitles Set` — 섹션 간 중복 제목 방지
- 공급망전쟁 섹션을 첫 번째로 배치 (간판 카테고리 강조)
- 최근 2일치 아카이브 자동 로드 → "최근 기사" 섹션
- 속보 포맷 badge 구분 (FACT + ACTION만 표시)
- 사이드바 검색창 → search.html?q= 연결
- 푸터 링크 실제 페이지 연결 (about, advertising, privacy, terms)
- 모바일 cat-grid: 420px에서도 2열 유지

---

## 기사검수.py 사용법

```bash
# 오늘 기사 검수
python 기사검수.py

# 특정 날짜 아카이브 검수
python 기사검수.py --date 2026-07-03
```

**검수 항목:**
- 5단계 필드 완성도 (각 최소 2단락)
- 속보(is_brief=True)는 fact/action만 검사
- 이미지 누락·중복 (MD5 해시)
- 카테고리 비중 (공급망전쟁 50% 목표)
- action 마지막 단락 현장 경험 패턴
- Telegram 알림 (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 환경변수)
- 로그: `scripts/review.log`

---

## 로컬 실행

```bash
cd "200 News_manager/202 The Signal Korea"
export ANTHROPIC_API_KEY="sk-ant-..."
export UNSPLASH_ACCESS_KEY="..."   # 선택
export PEXELS_API_KEY="..."        # 선택
pip install anthropic feedparser requests
python 기사자동생성.py
python 기사검수.py                  # 검수
```

---

## 배포 체크리스트

- [ ] GitHub 저장소 생성: `tugman77/the-signal-korea`
- [ ] 코드 push (index.html, article.html, category.html, search.html, about.html, advertising.html, privacy.html, terms.html, 기사자동생성.py, 기사검수.py 등)
- [ ] `ANTHROPIC_API_KEY` Secret 등록
- [ ] `UNSPLASH_ACCESS_KEY` Secret 등록 (선택)
- [ ] `PEXELS_API_KEY` Secret 등록 (선택)
- [ ] `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` Secret 등록 (선택)
- [ ] **GitHub Pages 활성화** (Settings → Pages → main / root)
- [ ] GitHub Actions 자동기사생성.yml 확인 (기사검수.py 스텝 추가 권장)
- [ ] 첫 실행: `workflow_dispatch`로 수동 트리거
- [ ] 메인 CLAUDE.md 대시보드 업데이트

---

## 201 소재경제신문과의 차이점

| 항목 | 201 소재경제신문 | 202 The Signal Korea |
|------|---------------|---------------------|
| 콘텐츠 | 반도체·소재·희귀금속 | 기술패권·공급망전쟁·산업전략 |
| 타깃 독자 | 산업 관계자 | 개인 투자자 |
| 기사 포맷 | body 배열 (10~13단락) | 5단계 별도 필드 + 이원 포맷 |
| 차별화 | 소재 전문 정보 | 조달 현장 경험 + 투자 관점 |
| 디자인 | 네이비+레드, 전통 신문 | 다크 네이비+골드, 프리미엄 인텔리전스 |
| 스케줄 | KST 09:00 | KST 09:00 |
