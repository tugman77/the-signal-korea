# 202 더 시그널 코리아 — CLAUDE.md (v2)

## 개요
글로벌 기술·산업 패권 뉴스를 분석해 "한국 산업은 앞으로 무엇으로 먹고 살 것인가?"에 답하는 인텔리전스 미디어.
**5단계 고정 프레임**: Fact → Meaning → Winner → Loser → Action

- **GitHub 저장소(라이브):** `tugman77/the-signal-korea` — 운영 중
- **라이브 URL:** https://tugman77.github.io/the-signal-korea
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
├── sojaetimes/             ← 전문 인텔리전스 파이프라인 (2026-07-16 추가)
│   ├── collect.py          ← 4개 분야 수집 (네이버API + Google RSS)
│   ├── agent_prompt.md     ← RemoteTrigger 저널리스트 브리핑 프롬프트
│   └── briefing_YYYY-MM-DD.json  ← 수집 결과 (GitHub Actions에서 생성)
└── .github/workflows/
    └── 자동기사생성.yml     ← GitHub Actions (매일 UTC 00:00 = KST 09:00)
```

### sojaetimes 파이프라인 (2026-07-16)
- `collect.py`: 공급망전쟁/기술패권/산업전략/글로벌분석 4개 분야 뉴스 수집
- `기사자동생성.py`: `load_sojaetimes_briefing()` → 공급망전쟁 이슈 프롬프트 우선 반영
- Actions 실행 순서: collect.py → 기사자동생성.py → 기사검수.py → push

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

## 이미지 관리 (기사자동생성.py v3 — 소재타임스 방식)

### 소스 우선순위
1. **Unsplash API** — `photos/random?count=10`으로 후보 10장 받아 미사용분 선택 (UNSPLASH_ACCESS_KEY)
2. **Pexels API** — 후보 10장 중 무작위 (PEXELS_API_KEY)
3. **Pixabay API** — 후보 10장 중 무작위 (PIXABAY_API_KEY)
4. **큐레이션 풀** — 카테고리별 photo-ID 8~9장 (`_UNSPLASH_POOL`, 키 없어도 항상 작동)
5. **picsum** (최후 수단)

### 3중 중복방지 (소재타임스 이식)
1. **Cross-category 중복 금지** — `_UNSPLASH_POOL` 각 photo-ID는 단일 카테고리에만. `_validate_pool()`이 실행마다 감지.
2. **Run 내 재사용 금지** — `_used_photo_ids` set.
3. **바이너리 중복 금지** — `_downloaded_hashes` set (MD5). 중복 시 저장 거부 후 다음 소스.

### 날짜 간 반복 방지
- `image_history.json` — photo-ID 마지막 사용 날짜 + MD5 해시 이력을 run 간 유지 (LRU로 가장 오래된 사진 우선 선택).
- 파일 미존재 시 `images/` 폴더를 스캔해 해시 복원 → 커밋된 이미지 기준 중복 차단.
- 워크플로 `git add`에 `image_history.json` 포함.

> ⚠️ **핵심**: 이미지 API 키(Unsplash 등)가 미등록이면 항상 4순위 풀로 떨어진다. 반드시 최소 1개 이상 등록할 것 (무료). 키가 있어야 기사 내용과 매칭되는 매일 다른 사진이 온다.

이미지 파일명: `images/YYYY-MM-DD_article_N.jpg`

### 이미지 배정 규칙 (2026-07-18 버그픽스 · 필독)
1. **파일명 N = 기사의 배열 위치(0-based), id와 반드시 일치.**
   - 이미지는 `download_article_images()`에서 `enumerate` 위치로 저장(`article_{i}.jpg`)한다.
   - 반면 Claude가 만드는 `id`는 1-based일 수 있어, 과거 `기사검수.py`가 **id로 재다운로드 경로를 계산**해 다른 기사 이미지를 덮어써 **중복·무관 사진**이 발생했다.
   - 조치: `기사자동생성.py`가 dedup 직후 **id를 배열 위치(0-based)로 정규화**한다. 데이터를 손으로 만들거나 고칠 때도 `id == 배열 위치`를 지킬 것.
2. **재다운로드는 기사의 실제 `image_url` 경로에만 덮어쓴다.** id로 경로를 새로 계산하지 말 것(`기사검수.py apply_image_keyword_fixes`).
3. **`image_keyword`는 촬영 가능한 구체적 사물 중심 영문 2~4단어.** 국가명·지명(Korea, Seoul, China)·추상어(strategy, policy, supply chain)는 금지 — 도시 전경·국기 등 무관 사진의 원인. 예: `gallium metal ingot`, `rare earth magnet`, `semiconductor wafer cleanroom`.
4. **검수 자동 감지**(`check_images`, API 키 불필요): ① 두 기사가 같은 `image_url` 참조 시 중복 경고, ② `image_url` 파일명이 자기 위치(`article_{i}.jpg`)와 다르면 불일치 경고. 텔레그램 보고에 포함.

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

## 수정 이력 (2026-07 버그픽스)

- **히어로 제목 겹침** (index.html): `.top-thumb` 의 `letter-spacing: -4px` 를 히어로 h2 오버레이가 상속 → `.top-thumb-overlay { letter-spacing: normal }` 추가로 해결.
- **핵심시그널 검정칸** (index.html): `.signal-label` 다크배경 정의가 사이드바 핵심시그널 라벨에까지 상속 → 티커바로 스코프 축소(`.signal-bar .signal-label { ... }`)해 해결. (article.html은 `signal-label-txt` 사용해 무관)
- **카테고리·검색 중복 기사** (category.html, search.html): 오늘 기사 + 아카이브 병합 시 제목 기준 `Set` 중복 제거 필터 적용(첫 등장만 유지).
- **쿠팡 광고 연속 노출** (article.html): 하단에 몰려 있던 캐러셀 광고 1개를 본문 중간(MEANING↔WINNER 사이)으로 이동, 하단은 리더보드 배너만 유지.
- **속보 빈 섹션 노출** (article.html, 2026-07-18): 속보(is_brief) 기사는 meaning/winner/loser가 빈 배열인데도 섹션 헤더가 그대로 렌더링됐다. `renderParagraphs()`가 내용 없는 섹션은 `.frame-section`째 숨기고, `renumberFrames()`가 남은 섹션 번호를 ①부터 다시 부여. is_brief 기사에는 카테고리 옆 "⚡ 속보" 배지 + 요약 아래 포맷 안내문 표시(FACT·ACTION만 전달하는 속보임을 명시).
- **이미지 중복·무관 사진** (기사자동생성.py, 기사검수.py, 2026-07-18): 파일명은 배열 위치(`article_{i}`)로 저장되나 검수의 재다운로드가 기사 `id`(1-based)로 경로를 계산 → id≠위치 시 남의 이미지를 덮어써 중복 발생. 조치는 위 "이미지 관리 › 이미지 배정 규칙" 절 참조.

---

## 기사검수.py 사용법

```bash
# 오늘 기사 검수
python 기사검수.py

# 특정 날짜 아카이브 검수
python 기사검수.py --date 2026-07-03
```

**검수 항목:**

*구조 검수 (API 키 없이도 동작)*
- 5단계 필드 완성도 (각 최소 2단락)
- 속보(is_brief=True)는 fact/action만 검사
- 이미지 파일 누락·용량·중복 (MD5 해시)
- 카테고리 비중 (공급망전쟁 50% 목표)
- action 마지막 단락 현장 경험 패턴

*Claude 검수 (2026-07-15 추가 · `ANTHROPIC_API_KEY` 필요, 소재타임스와 동일 방식)*
- **사실성 검증**: `trust_score`(1~5) + `status`(pass/warning/fail) + 의심 주장(`suspicious_claims`) — 기업·수치·법/정책명·인용·사건 개연성 점검
- **이미지 내용 연관성**: `image_keyword`가 기사 내용과 맞는지 판정 → 부적절 시 키워드 자동 수정 + 이미지 재다운로드(`기사자동생성.py`의 `_download_single_image` 재사용, 재다운로드엔 `UNSPLASH_ACCESS_KEY` 등 권장)
- 결과를 각 기사에 `review` 필드 + `last_reviewed_at`로 `articles.json`에 저장
- API 키 없으면 이 단계만 건너뛰고 구조 검수는 정상 수행

**보고**: 소재타임스식 텔레그램 보고 — 기사별 상태 이모지·신뢰도·의심주장·이미지 키워드 수정·자동 조치 요약 (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 필요)
**로그**: `scripts/review.log`

### 텔레그램 보고 문제해결 (2026-07-15)

`send_telegram()`은 실패 시 HTTP 상태코드뿐 아니라 텔레그램 응답의 `description`까지 로그에 남긴다 → `scripts/review.log`에서 정확한 사유 확인 가능.

| 증상 | 원인 | 조치 |
|------|------|------|
| `403 Forbidden` | 봇이 해당 대화에 메시지 권한 없음 | 텔레그램에서 봇에게 `/start` 누르기(1:1) 또는 그룹에 봇 초대 |
| `400 Bad Request: chat not found` | `TELEGRAM_CHAT_ID` 값이 틀림(오타·공백, 그룹인데 `-100` 접두어 누락) | 아래 getUpdates로 실제 chat_id 확인 후 Secret 재등록 |
| `400 Bad Request: can't parse entities` | HTML 파싱 오류(태그 불일치) | 메시지 본문 특수문자 이스케이프 확인 |

**정확한 chat_id 찾기 (워크플로 재실행 불필요, 로컬):** 봇에게 아무 메시지나 보낸 뒤
```bash
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getMe"      # 토큰 유효성·봇 username 확인
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates" # result[].message.chat.id 가 실제 chat_id
```
`getUpdates`에 나온 `chat.id`를 `TELEGRAM_CHAT_ID` Secret에 넣으면 해결. (봇 토큰은 `read -s`로 입력받아 노출 금지)

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

- [x] GitHub 저장소 생성: `tugman77/the-signal-korea` — 완료 (라이브 운영 중)
- [x] 코드 push (index/article/category/search/about/advertising/privacy/terms.html, 기사자동생성.py 등)
- [x] `ANTHROPIC_API_KEY` Secret 등록
- [x] `UNSPLASH_ACCESS_KEY` Secret 등록 완료 (2026-07-18) — 기사 내용 매칭 사진의 핵심 조건
- [ ] `PEXELS_API_KEY` Secret 등록 (선택)
- [x] `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` Secret 등록 완료 (전송 실패 시 위 "텔레그램 보고 문제해결"로 chat_id 확인)
- [x] **GitHub Pages 활성화** (Settings → Pages → main / root)
- [x] GitHub Actions 자동기사생성.yml 매일 KST 09:00 정상 동작
- [ ] 메인 CLAUDE.md 대시보드 업데이트

---

## ⚠️ 배포 게이트웨이 주의사항 (필독)

이 저장소는 **계정이 두 개** 얽혀 있어 잘못 푸시하면 라이브에 반영이 안 된다.

### 1. 라이브 저장소는 `tugman77/the-signal-korea` 하나뿐
- 라이브 = **tugman77** 계정. `https://tugman77.github.io/the-signal-korea` 가 실제 서비스.
- `ganddanbiz/the-signal-korea` 는 **미러/오배포용** — Pages 404, 서비스 안 됨.
- **로컬 `origin` remote가 ganddanbiz를 가리키고 있음.** ganddanbiz PAT는 tugman77 저장소에 **읽기 전용(push: False)**.
  → `git push origin main` 하면 **엉뚱한 저장소(ganddanbiz)로 가서 라이브에 안 뜬다.**
- 반영하려면 **tugman77 계정 PAT**(scope `repo`)로 명시 푸시:
  ```
  git push "https://tugman77:<PAT>@github.com/tugman77/the-signal-korea.git" <브랜치>:main
  ```
  PAT는 `read -s`로 입력받아 화면·기록에 노출 금지.

### 2. 워크플로 파일은 `workflow` 스코프 PAT 필요
- `.github/workflows/자동기사생성.yml` 을 변경·푸시하려면 PAT에 **`workflow` 스코프**가 있어야 함.
- 없으면 `refusing to allow a Personal Access Token to create or update workflow ... without workflow scope` 거부.
- HTML/데이터만 푸시할 땐 워크플로 파일을 커밋에서 제외(soft reset)하고 보낼 것.

### 3. 매일 자동생성이 main을 전진시킨다 → force-push 금지
- 워크플로가 매일 KST 09:00 **데이터 파일만** 갱신(articles.json, archive/*, images/) 커밋 push.
- HTML은 건드리지 않으므로, HTML 수정은 한 번 반영하면 이후에도 유지됨.
- 수정 배포 시 **최신 main 위에 cherry-pick 후 fast-forward** 로 올려야 자동생성 데이터를 덮어쓰지 않는다. **절대 force-push 하지 말 것.**

### 4. 반영 확인
- 푸시 성공(`... -> main`) 후 GitHub Pages 재빌드까지 ~1분.
- 라이브 검증은 `curl -s https://tugman77.github.io/the-signal-korea/index.html` 로 수정 코드가 들어갔는지 확인.

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
