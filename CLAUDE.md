# 202 더 시그널 코리아 — CLAUDE.md (v2)

## 개요
글로벌 기술·산업 패권 뉴스를 분석해 "한국 산업은 앞으로 무엇으로 먹고 살 것인가?"에 답하는 인텔리전스 미디어.
**5단계 고정 프레임**: Fact → Meaning → Winner → Loser → Action

- **GitHub 저장소(라이브):** `tugman77/the-signal-korea` — 운영 중
- **라이브 URL:** https://www.thesignalkorea.co.kr (커스텀 도메인, 2026-07-23 연결) · 원본 https://tugman77.github.io/the-signal-korea
- **커스텀 도메인:** 기본 `www.thesignalkorea.co.kr` (저장소 루트 `CNAME` 파일). 비아웹 DNS가 apex A 레코드를 지원하지 않아 **www 기본 + 루트 포워딩** 방식. `www` CNAME → `tugman77.github.io`, 루트 `thesignalkorea.co.kr`는 비아웹 포워딩으로 `https://www.thesignalkorea.co.kr`로 이동.
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
- 최근 10일 발행분(제목+요약) + **토픽 쿨다운 원장** → 중복 주제 방지 (아래 "반복 주제 관리" 절)
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

> **2026-08-02 대개편** — 소재타임스에서 검증된 이미지 모듈 3종을 이식했다.
> `이미지필터.py`(오매칭 방지) · `이미지소스.py`(외부 API) · `이미지풀.py`(큐레이션 풀).
> 세 파일은 두 채널이 **같은 구조**를 쓴다. 한쪽에서 버그를 고치면 다른 쪽도 함께 봐야 한다.

### 소스 우선순위
소스 목록은 `이미지소스.available_sources()` 한 곳에서 키 등록 상태를 보고 결정한다.
1. **Unsplash API** — 후보 10장을 받아 오매칭을 거른 뒤 하나씩 소비 (UNSPLASH_ACCESS_KEY)
2. **Pexels API** — 후보 10장을 `alt`로 필터 (PEXELS_API_KEY)
3. **Pixabay API** — 후보 10장을 `tags`로 필터 (PIXABAY_API_KEY)
4. **큐레이션 풀** — 로컬 self-host + Unsplash hotlink **82장** (키 없어도 항상 작동)
5. **picsum** — 최후 수단. **내용 무관 랜덤이라 여기까지 오면 사실상 실패다.**

### 오매칭 방지 (`이미지필터.py`)
- **검색 전** `refine_keyword()` — `wafer`·`chip`·`foil`·`plant` 등 일상 사물로도 읽히는
  단어에 업계 한정어를 자동 부착 (`"wafer production"` → `"wafer production semiconductor"`).
- **검색 후** `is_offtopic()` — 이미지 태그·alt에 음식·생활 차단어가 있으면 거부하고
  같은 소스의 다음 후보로. 실측상 Pixabay는 `wafer` 검색에 초콜릿·과자를 6~9장씩 반환한다.
- 차단어에 `wafer`·`plate`·`sheet`·`crystal`을 넣지 말 것 — 반도체·철강 사진의 정상 태그다.
- 수정 후 `python3 이미지필터.py`로 자가 검증 통과 필수.

### 3중 중복방지
1. **Cross-category 중복 금지** — 각 photo-ID는 단일 카테고리에만. `이미지풀.validate()`가 감지.
2. **Run 내 재사용 금지** — `_used_photo_ids` set.
3. **바이너리 중복 금지** — MD5 대조. **대조 범위가 소스에 따라 다르다:**
   - 외부 API·picsum → `_downloaded_hashes` (과거 날짜 포함 **영구**)
   - 큐레이션 풀 → `_run_hashes` (**이번 실행만**)

> ⚠️ **큐레이션 풀 MD5를 영구 히스토리에 넣지 말 것.** 풀 URL은 고정이라 매일 같은 바이트가
> 내려온다. 영구 해시에 넣는 순간 그 photo-ID는 두 번 다시 통과하지 못한다.
> 이식 시점(2026-08-02)에 이 채널은 **34장 중 18장(52%)이 이미 그렇게 죽어** picsum 폴백
> 직전이었다. 소재타임스는 88%까지 진행돼 OLED 기사에 갈매기 사진이 실렸다.
> 풀의 날짜 간 반복 간격은 `_photo_id_last_used` LRU가 맡는 것이 원래 설계다.

### 풀 늘리는 법 — `scripts/풀수집.py`
```bash
python3 scripts/풀수집.py 수집          # 카테고리별 후보 → images/pool/_후보/
python3 scripts/풀수집.py 대지          # 번호 붙은 컨택트시트 → 눈으로 고르기
python3 scripts/풀수집.py 확정 기술패권 "4,5,14,19"   # 고른 번호만 편입
python3 이미지풀.py                     # 장수 + cross-category 중복 점검 (필수)
```
- 편입 후 **1280×720(16:9) 리사이즈** 필수. API 원본은 1900px대라 저장소가 붓는다.
- `_후보/`는 `.gitignore` 대상.
- **최종 선별은 반드시 사람이 한다.** 실제로 후보에 여행객 단체사진·장난감 로봇·산 풍경이
  섞여 나왔다. 코드 주석도 믿지 말 것 — 이 채널 기존 풀은 "반도체 웨이퍼"로 주석된 ID가
  실제로는 납땜 사진이었다.

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

## 기사 생성 배치 분할 (2026-08-04) — 출력 32,000토큰 상한 대응

**증상:** 07-25~08-04 로컬 구독발행이 연속 실패. `RuntimeError: claude 헤드리스 실패(rc=1)`,
응답은 매번 `output_tokens: 32000` · `is_error: true` · `num_turns: 1`.

**원인은 사용량 한도가 아니다.** 로그에 429·usage limit 문구가 한 줄도 없다. 기사 5건을
한 호출로 뽑으면서 **헤드리스 출력이 32,000토큰 상한에 걸려 JSON이 잘린 것**이다.
시그널은 5단계 프레임(fact/meaning/winner/loser/action)이라 소재타임스보다 기사당 출력이 크다.
발행 시각을 03:40→08:15로 옮긴 것(창 분리)은 한도 여유를 준 것이지 이 버그와는 무관하다.

**조치:** `generate_articles_with_claude()`가 **3건 + 2건 두 배치**로 나눠 호출한다.

| 배치 | 건수 | 카테고리 | is_featured |
|---|---|---|---|
| 1 | 3 | 공급망전쟁 2 · 기술패권 1 | 첫 기사만 true |
| 2 | 2 | 산업전략 1 · 공급망전쟁\|글로벌분석 1 | 전부 false (코드로 강제) |

합치면 기존 비중 규칙(공급망전쟁 2~3 / 기술패권 1~2 / 산업전략 1 / 글로벌분석 0~1)을 만족한다.

- **배치2는 배치1 결과를 프롬프트에 받는다** — `[오늘 이미 작성한 기사]` 블록에 제목·`topic_key`·
  `image_keyword`를 실어 같은 날 안에서의 중복을 막는다. 한 호출로 뽑을 때 프롬프트가 하던
  "5개 기사는 서로 달라야 한다"는 제약을 대신하는 장치다.
- 스키마의 `minItems`/`maxItems`는 배치 건수로 바뀐다. `is_brief`는 배치당 최대 1개.
- `is_featured`는 병합 후 **앞의 하나만** 남긴다(index.html 히어로가 이 값을 본다).
- API코인 경로(GitHub Actions)도 같은 배치를 탄다 — 코드 경로가 하나라서다. 프롬프트가 2회
  들어가므로 입력 토큰이 늘지만, 클라우드는 로컬 실패 시에만 도는 백업이라 영향이 작다.

> 배치 수를 다시 조정할 땐 **한 배치가 3건을 넘지 않게** 할 것. 5건이 32,000을 넘겼다.

> ⚠️ **배치 분할만으로는 부족했다 (2026-08-06 정정).** 3건 배치도 `--effort medium`에서는
> 출력 29,491토큰으로 상한 바로 밑에 붙어, 실행에 따라 32,000을 넘겨 턴이 갈렸다.
> **사고(thinking) 토큰도 같은 32,000 출력 예산을 먹는다**는 점을 8/4 조치가 놓쳤다.
> 지금은 `기사자동생성.py`가 생성 호출에 `effort="low"`를 넘긴다 → 사고 0자, 출력
> 13,702토큰(여유 57%), 소요 561초 → 247초. 산출물은 5단계 단락 수·현장 경험 문단·
> 금지표현·카테고리 쿼터를 모두 지켰다. **검수 호출은 기본값(medium) 그대로** 둔다 —
> 출력이 작아 상한 위험이 없고 판단 품질이 더 중요하다.

---

## 헤드리스 무응답 — 작업 디렉터리 TCC (2026-08-06) ⚠️ 필독

**증상:** 08-05·08-06 로컬 구독발행이 `claude 헤드리스 2회 모두 타임아웃(무응답)`으로 실패.
출력이 **한 줄도 없고** 세션 로그(`~/.claude/projects/**`)조차 생기지 않는다.

**배치 분할 탓이 아니다.** 코드를 하나도 안 바꾼 **소재타임스도 같은 날(08-05)부터 같은 증상**으로
죽었다. 두 채널의 `llm_backend.py`는 바이트 단위로 동일하다. 08-02~08-04의 32,000토큰 상한
실패(`rc=1`)와는 **다른 고장**이다 — 그쪽은 응답이 오긴 왔다.

**원인:** claude는 기동 직후 `getcwd()` → `open()`으로 작업 디렉터리를 연다. cwd가 `~/Desktop`
아래면 macOS **TCC**가 동의를 요구하는데, launchd 백그라운드 잡에는 동의 창을 띄울 상대가 없어
`open()`이 **영원히 블록**된다. API 요청은 시작조차 못 하므로 호출부에는 무응답으로만 보인다.

**방아쇠는 CLI 자동 업데이트다.** 08-04 22:04에 2.1.221이 깔렸고, 그 뒤 첫 launchd 실행부터
두 채널이 동시에 죽었다. TCC 승인은 **바이너리 경로·서명 단위**인데 자동 업데이트는
`versions/<새버전>`에 새 바이너리를 깐다 → 바이너리에 권한을 부여해 두는 방식은 **다음 업데이트에
또 깨진다.**

**조치:** `llm_backend.py`의 `CLAUDE_CODE_CWD`가 헤드리스 프로세스를 `$TMPDIR/aios-headless`
에서 돌린다. 프롬프트는 자체 완결형이라 저장소 파일을 참조하지 않으므로 결과물에는 영향이 없다.
(`CLAUDE_CODE_CWD` 환경변수로 덮어쓸 수 있으나 **Desktop 아래를 지정하면 안 된다.**)

**실측** (launchd·같은 바이너리·같은 환경, "1+1" 프롬프트):

| cwd | 결과 |
|---|---|
| `~/Desktop/…/시그널코리아` | 무한 대기 (열린 네트워크 연결 0건, `__getcwd`에서 블록) |
| `$TMPDIR/aios-headless` | 13초 정상 완료 |

**덤:** 저장소 CLAUDE.md(30KB)를 매 호출 컨텍스트에 싣지 않게 되어 캐시 입력이
22,073토큰 → 6,404토큰으로 줄었다.

> 진단 요령: 무응답 실패를 만나면 **먼저 세션 로그가 생겼는지** 본다
> (`ls -lt ~/.claude/projects/<프로젝트>/`). 없으면 API에 닿기 전에 죽은 것이므로
> 토큰·한도·프롬프트를 의심할 필요가 없다. 멈춘 프로세스는 `sample <PID>`로 스택을 뜬다.

---

## 반복 주제 관리 (토픽 쿨다운, 2026-07-23)

날짜 간 같은 토픽(고려아연 갈륨·미중 AI칩 등)이 제목만 바꿔 재발행되던 문제를 토픽 단위로 관리한다. **추가 API 호출 없음** — 생성 1회 안에서 처리.

1. **토픽키(`topic_key`)**: 각 기사에 사건 단위 정규화 키를 부여(예: `고려아연-갈륨-국내생산`, `미중-AI칩-수출통제`). 표현이 달라도 같은 사건이면 같은 키 → 문자열 제목 비교가 놓치는 "단어만 바꾼 재탕"을 잡는 신호.
2. **원장(`scripts/topic_history.json`)**: `{토픽키: 마지막 발행일}`. 워크플로 `git add`의 `scripts/`에 포함돼 run 간 유지. 30일 지난 항목은 자동 정리. (`TOPIC_HISTORY_FILE`)
3. **쿨다운(`TOPIC_COOLDOWN_DAYS`=7)**: 최근 7일 내 다룬 토픽은 프롬프트의 `[최근 다룬 토픽 — 쿨다운]` 블록에 '경과일'과 함께 주입. **"새로운 전개(신규 수치·사건·정책 변화)"가 있을 때만** 재발행하고 그 변화점을 제목·FACT에 명시하도록 강제. 없으면 다른 주제 선택.
4. **최근 창 확대(`RECENT_CONTEXT_DAYS`=10)**: 프롬프트에 넣는 최근 발행분을 3일 제목 → **10일 제목+요약**으로 확대(`get_recent_titles`). 요약까지 줘서 같은 토픽 인지도를 높임.
5. **모니터링**: 생성 후 쿨다운 토픽이 재등장하면 로그에 경고(`⚠️ 쿨다운 내 토픽 재등장`) — 새 전개 반영분인지 사후 확인용.

> 조정: 쿨다운 기간은 `TOPIC_COOLDOWN_DAYS`, 최근 창은 `RECENT_CONTEXT_DAYS` 상수만 바꾸면 됨. 토픽키가 실제 사건과 안 맞으면 원장을 손봐도 되나, 다음 run이 새 키를 기록하며 자가 보정된다.

---

## 배포·확산 체계 — "널리 알리기" (2026-07-28~30)

검색·공유·직접도달·SNS 4개 축을 **발행 파이프라인 안에서 자동 재생성**한다(추가 API 호출 없음). 관련 자산 생성기는 모두 맥 폰트 사용 → 로컬 발행 환경 전제.

### ① 검색 (SEO)
- `기사자동생성.py generate_seo_files()`: 발행 때마다 `sitemap.xml` + `rss.xml` 자동 재생성. URL은 정적 기사페이지(`news/{date}-{id}.html`) 기준.
- `robots.txt`(루트): `Allow: /` + `Sitemap:` 라인.
- `index.html`: OG/트위터 카드 + canonical + RSS 링크 + `NewsMediaOrganization` JSON-LD(정적).
- `article.html`: 기사별 OG/트위터 카드 + `NewsArticle` JSON-LD를 `injectMeta()`로 동적 주입.
- **소유확인 파일·메타 — 삭제 금지**: `index.html`의 `google-site-verification`/`naver-site-verification` 메타, 루트 `google821e470add1bdaa9.html`.
- 등록 현황: ✅ 구글 서치콘솔(소유확인+sitemap 제출), ✅ 네이버 서치어드바이저(소유확인+sitemap+rss 제출). 🔄 구글 뉴스 퍼블리셔 — 게시물·로고 준비 완료, [게시]만 남음.

> ⚠️ **검색등록은 반드시 www 속성.** 비아웹 apex(`thesignalkorea.co.kr`)는 HTTPS를 못 서빙(https 접속 시 000). GitHub Pages는 **www에만** 붙음. 속성은 `https://www.thesignalkorea.co.kr`(URL 접두어)로 만들 것. www 없는 속성은 "사이트를 찾을 수 없습니다"로 무조건 실패.

### ② 기사별 정적 공유페이지 — `정적페이지생성.py`
- 발행 시 `news/{date}-{id}.html`(본문 포함 정적페이지) 생성 → 크롤러·카톡 미리보기·OG용. index가 이걸 기본 링크로 사용.
- 공유버튼(X·스레드·텔레그램 share·링크복사) + 텔레그램 채널 구독 CTA 포함.
- 템플릿 수정 후 전체 재생성: `python 정적페이지생성.py`.

### ③ 직접도달 — 텔레그램 채널 @thesignalkorea
- 공개 채널 `t.me/thesignalkorea`에 매일 발행분 자동 푸시. 봇 **@Tugmanbot**을 채널 관리자로 추가함(Post Messages 권한 필수 — 없으면 403).
- `기사자동생성.py post_to_channel()`가 독자용 다이제스트(카테고리 이모지·요약·기사링크·해시태그) 발행. 관리자알림 `send_telegram()`과 분리, `TELEGRAM_CHANNEL_ID` 있을 때만 동작.
- 설정: GitHub 시크릿 `TELEGRAM_CHANNEL_ID=@thesignalkorea` + 로컬 `$BASE/.env` 동일 추가.

### ④ SNS 확산 — 카드뉴스 + 관리자 자동전송
- `카드뉴스생성.py`: 발행 시 기사별 1080×1080 브랜드 카드 `cards/{date}-{id}.png` 생성(Pillow, 네이비/골드). 맥 폰트 우선 + 리눅스 한글폰트 폴백, 폰트 없으면 깔끔히 스킵.
- `기사자동생성.py send_cards_to_admin()`: 발행 시 카드 5장을 **관리자 채팅(`TELEGRAM_CHAT_ID`)**으로 X·스레드 리포스트용 캡션(제목+news링크+해시태그)과 함께 sendPhoto 전송 → 대표님이 저장해 수동 업로드(**반자동**).
- 브랜드 자산 생성기: `scripts/make_og_image.py`(og-default.jpg), `scripts/make_logos.py`(로고 2종).
- **미구현(선택)**: X/Threads 직접 자동포스팅(API 토큰 필요 — X 유료, Threads Meta앱 심사), 투자 커뮤니티 시딩.

### 워크플로 반영
`.github/workflows/자동기사생성.yml`의 `git add`에 `sitemap.xml rss.xml news/ cards/` 포함, Generate 스텝 env에 `TELEGRAM_CHANNEL_ID` 추가. 로컬 `.command`는 `git add -A`라 자동 포함.

> ⚠️ **DNS**: www에 CNAME(→tugman77.github.io) 하나만 정상. A레코드(121.88.250.13)가 www에 붙으면 충돌 → 일부 DNS 접속 불가. 루트(@)만 포워딩. DNS 갈아엎지 말 것.

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
- [x] **배포·확산 체계 구축**(2026-07-30): SEO(sitemap/rss/robots/OG/구조화데이터) + 텔레그램 채널 @thesignalkorea + 기사별 정적 공유페이지 + 카드뉴스 관리자 자동전송 — 위 "배포·확산 체계" 절 참조
- [x] `TELEGRAM_CHANNEL_ID` Secret + 로컬 .env 등록 완료 (`@thesignalkorea`)
- [ ] 구글 뉴스 퍼블리셔 [게시] 눌러 검토 요청 (로고·게시물 준비 완료)
- [ ] 메인 CLAUDE.md 대시보드 업데이트

---

## ⚠️ 배포 게이트웨이 주의사항 (필독)

이 저장소는 **계정이 두 개** 얽혀 있어 잘못 푸시하면 라이브에 반영이 안 된다.

### 1. 라이브 저장소는 `tugman77/the-signal-korea` 하나뿐
- 라이브 = **tugman77** 계정. `https://tugman77.github.io/the-signal-korea` 가 실제 서비스.
- **현재 `origin` remote가 tugman77/the-signal-korea 를 가리킴**(2026-07 정정 — 과거 ganddanbiz 경고는 해소됨). `origin`과 `tugman77` remote는 **같은 저장소 URL**이며, `tugman77/main` 추적ref는 오래돼 뒤처져 보일 수 있으니 **`origin/main`을 기준**으로 볼 것.
- 로컬 keychain PAT에 `repo`+`workflow` 스코프가 있어 평소엔 그냥 `git push origin HEAD:main` 으로 반영된다.
  ```
  git push origin HEAD:main
  ```
  토큰이 필요하면 `read -s`로 입력받아 화면·기록에 노출 금지.

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
