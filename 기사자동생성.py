"""
더 시그널 코리아 (The Signal Korea) — 자동 기사 생성 스크립트 v2
실행: python 기사자동생성.py
필요: pip install anthropic requests feedparser

업그레이드 내역 (v3 — 이미지 반복 해결):
  - 이미지 우선순위: Unsplash(count=10) → Pexels → Pixabay → 큐레이션 풀(photo-ID) → picsum
  - 3중 중복방지: cross-category · run내 _used_photo_ids · MD5 해시(_downloaded_hashes)
  - image_history.json으로 날짜 간(run 간) 재사용 방지 + LRU 선택
  - 큐레이션 풀 카테고리당 8~9장으로 확장 (섹션 내 반복 제거)
  - 이미지 파일명에 날짜 포함: images/YYYY-MM-DD_article_N.jpg
  - 중복 주제 방지: 최근 3일 기사 제목 → 프롬프트에 전달
  - 기사 이원 포맷 분기: is_brief=True → FACT+ACTION만 생성
  - 프롬프트 강화: "실제 조달 현장에서는~" 현장 경험 문단 필수 삽입
  - 공급망전쟁 카테고리 비중 50% 유지 (5기사 중 2~3개)
  - SEO: image_keyword를 구체적 소재명 기반으로 생성
"""

import anthropic
import feedparser
import json
import os
import requests
import hashlib
import random
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "여기에_API키_입력")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")   # 선택 — 있으면 사용
PEXELS_API_KEY      = os.environ.get("PEXELS_API_KEY", "")        # 선택 — 있으면 사용
PIXABAY_API_KEY     = os.environ.get("PIXABAY_API_KEY", "")       # 선택 — 있으면 사용
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")

OUTPUT_FILE = "articles.json"
IMAGES_DIR  = "images"
IMAGE_HISTORY_FILE = "image_history.json"  # 날짜 간 photo-ID·MD5 이력 (run 간 재사용 방지)

# ════════════════════════════════════════════════════════
# 이미지 관리 규칙 (IMAGE RULES) — 소재타임스와 동일 방식
# ════════════════════════════════════════════════════════
# 1. 카테고리별 풀에 동일 photo-ID가 두 카테고리에 등록되면 안 된다
#    (_validate_pool()이 실행마다 자동 감지).
# 2. 한 실행(run) 안에서 이미 선택한 photo-ID는 재사용 금지 (_used_photo_ids).
# 3. 다운로드된 파일의 MD5가 이미 저장된 파일과 동일하면 다음 소스로 넘어간다
#    (_downloaded_hashes, image_history.json으로 날짜 간 유지).
# 4. 풀은 카테고리당 8개 이상(5기사/일 + 여유분)을 유지한다.
# ── 카테고리별 Unsplash 큐레이션 풀 (photo-ID) ──
# 규칙: 동일 photo-ID가 두 카테고리에 나타나서는 안 된다.
_UNSPLASH_POOL = {
    "공급망전쟁": [
        "photo-1494412519320-aa613dfb7738",  # 컨테이너 항구 항공뷰
        "photo-1578575437130-527eed3abbec",  # 컨테이너선 접안 항구
        "photo-1586528116311-ad8dd3c8310d",  # 물류 창고 내부
        "photo-1521790361543-f645cf042ec4",  # 화물 항공기
        "photo-1488229297570-58520851e868",  # 화물선 드론 항공뷰
        "photo-1527515637462-cff94eecc1ac",  # 채석장·광산 암반
        "photo-1531538606174-0f90ff5dce83",  # 광물·원석
        "photo-1565793298595-6a879b1d9492",  # 광산 덤프트럭
        "photo-1578375819537-b95e00c82429",  # 금속 제련 용광로
    ],
    "기술패권": [
        "photo-1518770660439-4636190af475",  # PCB 회로기판 클로즈업
        "photo-1591799265444-d66432b91588",  # CPU 칩
        "photo-1562408590-e32931084e23",     # PCB 회로기판 (파랑)
        "photo-1597852074816-d933c7d2b988",  # 전자 부품 내부
        "photo-1581092918056-0c4c3acd3789",  # 전자기기 납땜 작업
        "photo-1451187580459-43490279c0fa",  # 서버 데이터센터 랙
        "photo-1526374965328-7f61d4dc18c5",  # 코드 스크린
        "photo-1555680202-c86f0e12f086",     # 컴퓨터 마더보드
        "photo-1558494949-ef010cbdcc31",     # 광섬유 케이블
    ],
    "산업전략": [
        "photo-1567789884554-0b844b597180",  # 자동차 공장 로봇
        "photo-1473341304170-971dccb5ac1e",  # 고압 송전탑
        "photo-1541888946425-d81bb19240f5",  # 건설 현장 엔지니어
        "photo-1495576775051-8af0d10f68d1",  # 제철·철강 생산
        "photo-1504711434969-e33886168f5c",  # 제철소 용융 쇳물
        "photo-1565791380713-1756b9a05343",  # 화학 플랜트 항공뷰
        "photo-1582139329536-e7284fece509",  # 건설 크레인 군집
        "photo-1581092160607-ee22621dd758",  # 엔지니어 기계 작업
    ],
    "글로벌분석": [
        "photo-1586769852044-692d6e3703f0",  # 세계 공급망 지도
        "photo-1558618666-fcd25c85cd64",     # 글로벌 해운 항로
        "photo-1545193544-312489b2d26c",     # 물류 트럭 주차장
        "photo-1524522173746-f628baad3644",  # 글로벌 산업
        "photo-1565514020179-026b92b84bb6",  # 도시·산업 스카이라인
        "photo-1601597111158-2fceff292cdc",  # 기술·데이터 시각화
        "photo-1563770660941-20978e870e26",  # 반도체 웨이퍼
        "photo-1494412574643-ff11b0a5c1c3",  # 산업 설비
    ],
}
_UNSPLASH_BASE = "https://images.unsplash.com/{id}?w=800&h=450&fit=crop&auto=format"

RSS_FEEDS = [
    ("Google뉴스-공급망패권",  "https://news.google.com/rss/search?q=갈륨+게르마늄+수출+규제+한국+공급망&hl=ko&gl=KR&ceid=KR:ko"),
    ("Google뉴스-미중패권",    "https://news.google.com/rss/search?q=미중+반도체+패권+공급망&hl=ko&gl=KR&ceid=KR:ko"),
    ("Google뉴스-AI산업",      "https://news.google.com/rss/search?q=AI+반도체+한국+산업전략&hl=ko&gl=KR&ceid=KR:ko"),
    ("Google뉴스-글로벌공급망","https://news.google.com/rss/search?q=supply+chain+semiconductor+Korea+strategy&hl=en&gl=US&ceid=US:en"),
    ("Google뉴스-기술패권",    "https://news.google.com/rss/search?q=tech+war+US+China+chip+Korea&hl=en&gl=US&ceid=US:en"),
    ("연합뉴스 경제",          "https://www.yna.co.kr/rss/economy.xml"),
    ("전자신문",               "https://www.etnews.com/rss/section/"),
]

KST = timezone(timedelta(hours=9))


# ── 텔레그램 알림 ────────────────────────────────────────────────────
def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[텔레그램 미설정] {message[:80]}")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.ok
    except Exception as e:
        print(f"텔레그램 전송 오류: {e}")
        return False


# ── 제목 유사도 (2-gram Jaccard) ──────────────────────────────────
def title_similarity(t1: str, t2: str) -> float:
    """두 제목의 2-gram 자카드 유사도 (0.0~1.0). 0.7 이상이면 같은 뉴스로 간주."""
    if not t1 or not t2:
        return 0.0
    def bigrams(s):
        return set(s[i:i+2] for i in range(len(s) - 1))
    b1, b2 = bigrams(t1), bigrams(t2)
    if not b1 or not b2:
        return 0.0
    return len(b1 & b2) / len(b1 | b2)


# ── RSS 수집 결과 중복 제거 ────────────────────────────────────────
def deduplicate_rss(items: list) -> list:
    """같은 URL + 제목 유사도 70% 이상 항목 제거. 먼저 나온 것을 유지."""
    seen_urls: set = set()
    seen_titles: list = []
    result = []
    removed = 0

    for item in items:
        url   = item.get("link", "").strip()
        title = item.get("title", "").strip()

        # 1. URL 중복 제거
        if url and url in seen_urls:
            removed += 1
            continue
        if url:
            seen_urls.add(url)

        # 2. 제목 유사도 중복 제거
        is_dup = False
        for st in seen_titles:
            if title_similarity(title, st) >= 0.70:
                print(f"   중복 RSS 제거: '{title[:35]}' (유사: '{st[:35]}')")
                is_dup = True
                removed += 1
                break
        if is_dup:
            continue

        seen_titles.append(title)
        result.append(item)

    if removed:
        print(f"   → RSS 중복 {removed}건 제거 (남은 {len(result)}건)")
    return result


# ── 생성된 기사 내 제목 중복 제거 ─────────────────────────────────
def deduplicate_articles(articles: list) -> list:
    """생성된 기사 중 제목 유사도 70% 이상인 중복 제거. 먼저 나온 것을 유지."""
    seen_titles: list = []
    result = []
    removed = 0

    for article in articles:
        title = article.get("title", "")
        is_dup = False
        for st in seen_titles:
            sim = title_similarity(title, st)
            if sim >= 0.70:
                print(f"🚫 중복 기사 제거: '{title}' (유사도 {int(sim*100)}%, 유지: '{st}')")
                is_dup = True
                removed += 1
                break
        if is_dup:
            continue
        seen_titles.append(title)
        result.append(article)

    if removed:
        print(f"   → 기사 중복 {removed}건 제거 (확정 {len(result)}건)")
    return result


# ── RSS 수집 ───────────────────────────────────────────────────────
def collect_news_from_rss(max_per_feed=5):
    collected = []
    for name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title   = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))[:300]
                link    = entry.get("link", "")
                collected.append({"source": name, "title": title, "summary": summary, "link": link})
        except Exception as e:
            print(f"RSS 오류 [{name}]: {e}")
    return deduplicate_rss(collected)


# ── 최근 3일 기사 제목 추출 (중복 주제 방지) ──────────────────────
def get_recent_titles(days=3):
    recent_titles = []
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        recent_titles += [a.get("title", "") for a in data.get("articles", [])]
    except Exception:
        pass
    try:
        with open("archive/index.json", "r", encoding="utf-8") as f:
            idx = json.load(f)
        for dk in (idx.get("dates", []))[:days]:
            try:
                with open(f"archive/{dk}.json", "r", encoding="utf-8") as f:
                    d = json.load(f)
                recent_titles += [a.get("title", "") for a in d.get("articles", [])]
            except Exception:
                pass
    except Exception:
        pass
    return list(set(filter(None, recent_titles)))


# ── sojaetimes 브리핑 로드 ──────────────────────────────────────────
def load_sojaetimes_briefing() -> dict:
    date_key = datetime.now(KST).strftime("%Y-%m-%d")
    path = f"sojaetimes/briefing_{date_key}.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            briefing = json.load(f)
        total = briefing.get("total_count", 0)
        print(f"📊 sojaetimes 브리핑 로드: {total}건 ({date_key})")
        return briefing
    except FileNotFoundError:
        print(f"   → sojaetimes 브리핑 없음 ({path}), RSS만 사용")
        return {}


# ── Claude API로 기사 생성 ──────────────────────────────────────────
def generate_articles_with_claude(raw_news_list, recent_titles, sojaetimes_briefing=None):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    news_text = ""
    for i, item in enumerate(raw_news_list[:18], 1):
        news_text += f"{i}. [{item['source']}] {item['title']}\n   {item['summary']}\n\n"

    if news_text:
        news_section = f"[수집된 원본 뉴스]\n{news_text}\n원문을 참고해 핵심 내용을 바탕으로 새로운 문장으로 작성하세요."
    else:
        news_section = "[원본 뉴스 없음]\n최근 글로벌 기술·산업 패권 동향(반도체 수출 통제, AI 공급망, 소부장 재편 등)을 바탕으로 작성하세요."

    recent_block = ""
    if recent_titles:
        recent_list = "\n".join(f"  - {t}" for t in recent_titles[:20])
        recent_block = f"""
[이미 다룬 주제 — 반드시 피할 것]
아래 제목과 동일하거나 매우 유사한 주제의 기사는 절대 작성하지 마세요:
{recent_list}
"""

    # sojaetimes 브리핑 섹션 구성
    sojaetimes_section = ""
    if sojaetimes_briefing and sojaetimes_briefing.get("topics"):
        topic_labels = {
            "공급망전쟁": "공급망전쟁 (소재 수출규제·조달 병목)",
            "기술패권":   "기술패권 (미·중 반도체·AI 전쟁)",
            "산업전략":   "산업전략 (한국 소부장·정책)",
            "글로벌분석": "글로벌분석 (미·EU·일·인도 동향)",
        }
        lines = ["[sojaetimes 전문 인텔리전스 — 분야별 최우선 반영]", "━" * 44]
        for topic_key, label in topic_labels.items():
            items = sojaetimes_briefing["topics"].get(topic_key, [])[:4]
            if not items:
                continue
            lines.append(f"\n▶ {label}")
            for it in items:
                lang_tag = "[영]" if it.get("lang") == "en" else "[한]"
                lines.append(f"  {lang_tag} {it['title']}")
                if it.get("summary"):
                    lines.append(f"      → {it['summary'][:120]}")
        lines += [
            "",
            "특히 [공급망전쟁] 이슈를 최우선으로 검토하고, 공급망전쟁 카테고리 기사 2~3개에 반영하세요.",
        ]
        sojaetimes_section = "\n".join(lines) + "\n\n"

    prompt = f"""당신은 광학·반도체·디스플레이 소재를 20년간 직접 공급해온 현장 전문가입니다.
갈륨·게르마늄·비스무트·이트륨·마그네슘 등 핵심 소재를 국내외 기업에 실제 공급한 경험을 바탕으로,
지금은 소재 공급망 인텔리전스 분석가로 시장을 조망하며 칼럼을 씁니다.

[필자 관점 — 반드시 유지]
- 생산자도 수요자도 아닌 "공급자" 시각: 누가 어디서 뭘 사는지, 어디서 병목이 생기는지를 먼저 본다
- 뉴스가 되기 전에 이미 현장에서 신호를 감지한 사람의 어조
- 단순 요약이 아니라 "내가 현장에서 봤을 때 이건 이런 의미다"는 직언 스타일
- 일반 언론이 놓치는 소재·거래·공급망의 실제 작동 방식을 짚어준다

핵심 미션: 글로벌 기술·산업 뉴스를 현장 공급망 시각으로 해석하여 "한국 산업은 앞으로 무엇으로 먹고 살 것인가?"에 답합니다.
타깃 독자: 개인 투자자·기업 구매담당자·산업 전략가 — "이 뉴스가 실제 비즈니스에 무슨 의미인가"에 답해야 합니다.

{sojaetimes_section}{news_section}

{recent_block}

[카테고리 비중 — 반드시 준수]
- 공급망전쟁: 5기사 중 2~3개 (50% 목표) — 갈륨·탄탈럼·희토류·리튬 등 소재 중심
- 기술패권:   1~2개 (20%)
- 산업전략:   1개   (20%)
- 글로벌분석: 0~1개 (10%)

[작성 규칙 — 절대 준수]
- 모호한 표현('비약적', '주목받는', '큰 영향', '급성장') 절대 금지
- 모든 주장에 정량 수치(시장 점유율%, 투자 규모, 연도, 법안명, 기업명) 필수
- 각 단계 최소 2개 이상 구체적 통계 수치 또는 기업명 포함
- 제목: 15~25자, 핵심 팩트·수치 중심 (예: "중국 갈륨 수출 99% 차단, 한국 연간 700억 리스크")
- summary: 2~3문장 핵심 요약 (150자 이내), 투자자 관점에서 서술
- image_keyword: 사진으로 촬영 가능한 구체적 사물·장면 중심의 영문 2~4단어. 예: "gallium metal ingot", "tantalum ore mineral", "semiconductor wafer cleanroom", "rare earth magnet", "data center server rack".
  · 국가명·지명(Korea, Seoul, China, US 등)과 추상어(strategy, policy, economy, market, supply chain)는 넣지 말 것 — 도시 전경·국기 같은 무관한 사진이 나온다.
- 중요: 5개 기사의 image_keyword는 서로 겹치지 않게 각기 다른 소재·사물·장면을 지목할 것 (같은 카테고리라도 시각 소재를 분산 — 갈륨 잉곳 vs 탄탈럼 광석 vs 데이터센터 서버 등)

[현장 경험 문단 — action 배열 마지막에 필수 삽입]
action 배열의 마지막 단락은 반드시 다음 형식으로 시작할 것:
"실제 조달 현장에서는 — [현장에서 관찰한 구체적 상황이나 패턴]. [이에 따른 실행 제언]."

[5단계 인텔리전스 프레임]
is_brief=false (주력 분석글):
- fact:    3~4개 단락, 각 150~250자
- meaning: 2~3개 단락
- winner:  2~3개 단락 (반사이익 국가·산업·기업 + 수치)
- loser:   2~3개 단락 (타격 플레이어 + 수치)
- action:  3~4개 단락 (마지막 단락은 반드시 "실제 조달 현장에서는 —"로 시작)

is_brief=true (속보성 글, 최대 1~2개):
- fact:    2~3개 단락
- meaning: [] (빈 배열)
- winner:  [] (빈 배열)
- loser:   [] (빈 배열)
- action:  2~3개 단락 (마지막 단락은 반드시 "실제 조달 현장에서는 —"로 시작)

save_articles 도구를 사용해 기사 5개를 저장하세요.
- 첫 번째 기사(is_featured: true)는 공급망전쟁 또는 기술패권으로 설정
- 나머지 4개: is_featured=false
- timestamp: 현재 시각 기준 오전/오후 HH:MM 형식
"""

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=32000,
        tools=[{
            "name": "save_articles",
            "description": "생성된 기사 5개를 저장합니다",
            "input_schema": {
                "type": "object",
                "properties": {
                    "articles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id":            {"type": "integer"},
                                "category":      {"type": "string", "enum": ["기술패권","공급망전쟁","산업전략","글로벌분석"]},
                                "tag_type":      {"type": "string", "enum": ["tag-hegemony","tag-supply","tag-strategy","tag-global"]},
                                "title":         {"type": "string"},
                                "summary":       {"type": "string"},
                                "is_brief":      {"type": "boolean"},
                                "fact":          {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
                                "meaning":       {"type": "array", "items": {"type": "string"}},
                                "winner":        {"type": "array", "items": {"type": "string"}},
                                "loser":         {"type": "array", "items": {"type": "string"}},
                                "action":        {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
                                "image_keyword": {"type": "string", "description": "기사 핵심 소재를 사진으로 촬영 가능한 구체적 사물 중심의 영문 2~4단어. 국가명·지명(Korea, Seoul, China 등)과 추상어(strategy, policy, economy, market)는 절대 금지. 예: 'gallium metal ingot', 'semiconductor wafer cleanroom', 'rare earth magnet', 'fiber optic cable' 처럼 실제 피사체가 명확해야 함."},
                                "is_featured":   {"type": "boolean"},
                                "timestamp":     {"type": "string"}
                            },
                            "required": ["id","category","tag_type","title","summary","is_brief",
                                         "fact","meaning","winner","loser","action",
                                         "image_keyword","is_featured","timestamp"]
                        },
                        "minItems": 5,
                        "maxItems": 5
                    }
                },
                "required": ["articles"]
            }
        }],
        tool_choice={"type": "tool", "name": "save_articles"},
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        response = stream.get_final_message()

    tool_block = next(b for b in response.content if b.type == "tool_use")
    articles = tool_block.input["articles"]
    if isinstance(articles, str):
        print("⚠️  articles가 str 타입, json_repair 시도...")
        try:
            from json_repair import repair_json
            articles = json.loads(repair_json(articles))
        except ImportError:
            articles = json.loads(articles)

    # 필드 정제
    for a in articles:
        for field in ["fact", "meaning", "winner", "loser", "action"]:
            val = a.get(field)
            if isinstance(val, str):
                a[field] = [p.strip() for p in val.split("\n") if p.strip()]
            elif val is None:
                a[field] = []
        # is_brief 기본값
        if "is_brief" not in a:
            a["is_brief"] = not bool(a.get("meaning"))

    return articles


# ── 편집장 브리핑 + 핵심 시그널 생성 ───────────────────────────────
def generate_editorial(articles):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    titles_text = "\n".join(
        f"- {a['title']}: {(a.get('summary') or '')[:80]}" for a in articles
    )

    prompt = f"""오늘 더 시그널 코리아 주요 기사:
{titles_text}

위 기사를 바탕으로 save_editorial 도구를 사용해:
1. briefing: 오늘 글로벌 기술·산업 패권 전체 흐름을 2~3문장으로 요약 (150자 이내, 편집장 코멘트 느낌, 투자자 관점)
2. signals: 현재 진행 중인 핵심 신호(Signal) 4~5개
   - icon: 🔴(위험/긴급) 🟡(주의/모니터링) 🟢(기회/긍정)
   - label: 시그널명 (15자 이내)
   - status: 상태 한 줄 (12자 이내)
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            tools=[{
                "name": "save_editorial",
                "description": "편집장 브리핑과 핵심 시그널을 저장합니다",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "briefing": {"type": "string"},
                        "signals": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "icon":   {"type": "string", "enum": ["🔴","🟡","🟢"]},
                                    "label":  {"type": "string"},
                                    "status": {"type": "string"}
                                },
                                "required": ["icon","label","status"]
                            },
                            "minItems": 4,
                            "maxItems": 5
                        }
                    },
                    "required": ["briefing","signals"]
                }
            }],
            tool_choice={"type": "tool", "name": "save_editorial"},
            messages=[{"role": "user", "content": prompt}]
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        briefing = tool_block.input["briefing"]
        signals  = tool_block.input["signals"]
        print(f"   → 브리핑 생성 완료, 시그널 {len(signals)}개")
        return briefing, signals
    except Exception as e:
        print(f"  편집국 생성 오류: {e} → 기본값 사용")
        return (
            "오늘 더 시그널 코리아는 공급망 재편과 기술 패권 경쟁의 핵심 시그널을 집중 분석합니다.",
            [
                {"icon": "🔴", "label": "미·중 소재 전쟁", "status": "격화"},
                {"icon": "🟡", "label": "공급망 재편",     "status": "진행 중"},
                {"icon": "🟡", "label": "AI 인프라 패권",  "status": "모니터링"},
                {"icon": "🟢", "label": "한국 소부장",     "status": "기회"},
            ]
        )


# ════════════════════════════════════════════════════════
# 이미지 다운로드 (3중 중복방지 + LRU) — 소재타임스와 동일 방식
# ════════════════════════════════════════════════════════
# _used_photo_ids / _downloaded_hashes 는 "이번 실행" 범위.
# _photo_id_last_used / (영구 hashes) 는 image_history.json 으로 "날짜 간" 유지된다.
_used_photo_ids: set    = set()   # 이번 실행에서 선택된 Unsplash photo-ID
_downloaded_hashes: set = set()   # 지금까지(과거 포함) 저장된 이미지 MD5
_photo_id_last_used: dict = {}    # photo-ID → 마지막 사용 날짜(YYYY-MM-DD)


def _load_image_history():
    """image_history.json 로드 → 과거 MD5 해시와 photo-ID 사용 이력을 메모리에 적재."""
    global _downloaded_hashes, _photo_id_last_used
    try:
        with open(IMAGE_HISTORY_FILE, "r", encoding="utf-8") as f:
            hist = json.load(f)
        _photo_id_last_used = dict(hist.get("photo_ids", {}))
        _downloaded_hashes  = set(hist.get("hashes", []))
    except (FileNotFoundError, json.JSONDecodeError):
        _photo_id_last_used = {}
        _downloaded_hashes  = set()
    # 이미 저장된 이미지 파일의 해시도 축적 (히스토리 파일이 없던 과거분 보완)
    if os.path.isdir(IMAGES_DIR):
        for fn in os.listdir(IMAGES_DIR):
            fp = os.path.join(IMAGES_DIR, fn)
            try:
                with open(fp, "rb") as f:
                    _downloaded_hashes.add(hashlib.md5(f.read()).hexdigest())
            except Exception:
                pass
    print(f"🗂️  이미지 히스토리 로드: 해시 {len(_downloaded_hashes)}개 · photo-ID {len(_photo_id_last_used)}개")


def _save_image_history():
    """이번 실행에서 갱신된 photo-ID 이력과 MD5 해시를 저장 (해시 최근 800개 보존)."""
    hashes = list(_downloaded_hashes)[-800:]
    data = {"photo_ids": _photo_id_last_used, "hashes": hashes}
    try:
        with open(IMAGE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"🗂️  이미지 히스토리 저장: 해시 {len(hashes)}개 · photo-ID {len(_photo_id_last_used)}개")
    except Exception as e:
        print(f"   → 히스토리 저장 오류: {e}")


def _validate_pool():
    """풀 내 cross-category 중복 photo-ID 감지 (로그 출력)."""
    seen = {}
    for cat, ids in _UNSPLASH_POOL.items():
        for pid in ids:
            if pid in seen:
                print(f"⚠️  중복 photo-ID: {pid} — {seen[pid]} ↔ {cat}")
            seen[pid] = cat


def _pick_pool_url(category: str, seed_str: str) -> tuple[str, str]:
    """카테고리 풀에서 photo-ID 선택. (url, photo_id) 반환.
      1. 이번 실행에서 아직 안 쓴 ID 중
      2. '가장 오래전에 사용(또는 미사용)' 그룹 우선(LRU) → 날짜 간 반복 간격 최대화
      3. 동률이면 시드 해시로 결정."""
    pool = _UNSPLASH_POOL.get(category) or _UNSPLASH_POOL["공급망전쟁"]
    available = [p for p in pool if p not in _used_photo_ids]
    if not available:
        available = pool  # 풀 소진 시 재사용 허용
    oldest_key = min(_photo_id_last_used.get(p, "") for p in available)
    tied = [p for p in available if _photo_id_last_used.get(p, "") == oldest_key]
    idx = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % len(tied)
    chosen = tied[idx]
    _used_photo_ids.add(chosen)
    return _UNSPLASH_BASE.format(id=chosen), chosen


def _record_photo_id(photo_id: str):
    """실제 저장에 사용된 photo-ID의 마지막 사용 날짜를 오늘로 기록."""
    if photo_id:
        _photo_id_last_used[photo_id] = datetime.now(KST).strftime("%Y-%m-%d")


def _fetch_pexels(keyword: str) -> str | None:
    """Pexels: 후보 10장 중 무작위 1장 URL 반환 (PEXELS_API_KEY 필요)."""
    if not PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": keyword, "per_page": 10, "orientation": "landscape"},
            headers={"Authorization": PEXELS_API_KEY}, timeout=15,
        )
        if r.status_code == 200:
            photos = r.json().get("photos", [])
            if photos:
                return random.choice(photos)["src"]["large2x"]
    except Exception as e:
        print(f"      Pexels 오류: {e}")
    return None


def _fetch_pixabay(keyword: str) -> str | None:
    """Pixabay: 후보 10장 중 무작위 1장 URL 반환 (PIXABAY_API_KEY 필요)."""
    if not PIXABAY_API_KEY:
        return None
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={"key": PIXABAY_API_KEY, "q": keyword, "image_type": "photo",
                    "orientation": "horizontal", "per_page": 10, "safesearch": "true"},
            timeout=15,
        )
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                return random.choice(hits)["largeImageURL"]
    except Exception as e:
        print(f"      Pixabay 오류: {e}")
    return None


def _download_single_image(keyword: str, img_path: str, category: str, seed_str: str) -> bool:
    """소스 우선순위(Unsplash count=10 → Pexels → Pixabay → 풀 → picsum)로 시도.
    MD5 중복이면 저장하지 않고 다음 소스로 넘어간다."""
    global _downloaded_hashes
    keyword_q = quote(keyword)
    seed = hashlib.md5(keyword.encode()).hexdigest()[:8]

    order: list[str] = []
    if UNSPLASH_ACCESS_KEY:
        order.append("unsplash_api")
    if PEXELS_API_KEY:
        order.append("pexels")
    if PIXABAY_API_KEY:
        order.append("pixabay")
    order += ["unsplash_pool"] * 8   # 중복 거부 시 다음 후보로
    order.append("picsum")

    pool_try = 0
    unsplash_candidates: list[str] = []  # count=10 후보 캐시
    for source in order:
        chosen_pid = None
        try:
            if source == "unsplash_api":
                # 후보 10장을 한 번에 받아 MD5 미사용인 것을 고른다
                if not unsplash_candidates:
                    r = requests.get(
                        f"https://api.unsplash.com/photos/random?query={keyword_q}"
                        f"&orientation=landscape&count=10&client_id={UNSPLASH_ACCESS_KEY}",
                        timeout=15,
                    )
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    if isinstance(data, dict):
                        data = [data]
                    unsplash_candidates = [
                        p.get("urls", {}).get("regular", "") for p in data
                    ]
                    unsplash_candidates = [u for u in unsplash_candidates if u]
                img_url = unsplash_candidates.pop(0) if unsplash_candidates else ""
                if not img_url:
                    continue
                # 아직 후보가 남아있으면 이 소스를 한 번 더 시도할 수 있게 재삽입
                if unsplash_candidates:
                    order.insert(order.index(source) + 1, "unsplash_api")
            elif source == "pexels":
                img_url = _fetch_pexels(keyword)
                if not img_url:
                    continue
            elif source == "pixabay":
                img_url = _fetch_pixabay(keyword)
                if not img_url:
                    continue
            elif source == "unsplash_pool":
                img_url, chosen_pid = _pick_pool_url(category, f"{seed_str}_{pool_try}")
                pool_try += 1
            else:
                img_url = f"https://picsum.photos/seed/{seed}/800/450"

            resp = requests.get(img_url, timeout=30, allow_redirects=True,
                                headers={"User-Agent": "TheSignalKorea/3.0"})
            if resp.status_code != 200 or len(resp.content) < 1000:
                continue

            img_hash = hashlib.md5(resp.content).hexdigest()
            if img_hash in _downloaded_hashes:
                print(f"      → 중복 이미지 [{source}] md5={img_hash[:8]}, 다음 소스 시도...")
                continue

            _downloaded_hashes.add(img_hash)
            _record_photo_id(chosen_pid)  # 풀 이미지일 때만 사용 날짜 기록
            with open(img_path, "wb") as f:
                f.write(resp.content)
            print(f"      → 이미지 저장: {img_path} [{category}] ({source})")
            return True

        except Exception as e:
            print(f"      → 이미지 오류 [{source}]: {e}")

    return False


def download_article_images(articles, date_str):
    """각 기사 이미지 다운로드 → images/YYYY-MM-DD_article_N.jpg
    _used_photo_ids만 run 단위로 초기화, _downloaded_hashes·_photo_id_last_used는
    image_history.json에서 로드해 날짜 간 재사용을 방지한다."""
    global _used_photo_ids
    _used_photo_ids.clear()
    _load_image_history()
    _validate_pool()

    os.makedirs(IMAGES_DIR, exist_ok=True)
    for i, article in enumerate(articles):
        keyword  = article.get("image_keyword", "technology industry Korea")
        category = article.get("category", "글로벌분석")
        seed_str = f"{date_str}_{i}_{article.get('title', '')}"
        img_path = f"{IMAGES_DIR}/{date_str}_article_{i}.jpg"
        print(f"   이미지 [{i}] 키워드: {keyword}")
        if _download_single_image(keyword, img_path, category, seed_str):
            article["image_url"] = img_path
        else:
            article["image_url"] = None
            print(f"      → 이미지 모두 실패 [{keyword}]")

    _save_image_history()
    return articles


# ── 데이터 저장 ──────────────────────────────────────────────────────
def save_data(articles, briefing, signals, date_str, date_key):
    now = datetime.now(KST)
    data = {
        "generated_at":    now.strftime("%Y년 %m월 %d일 %H:%M"),
        "date_str":        now.strftime("%Y년 %m월 %d일"),
        "articles":        articles,
        "editorial_briefing": briefing,
        "key_signals":     signals,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ {OUTPUT_FILE} 저장 완료 — 기사 {len(articles)}건")

    os.makedirs("archive", exist_ok=True)
    archive_file = f"archive/{date_key}.json"
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"📁 아카이브 저장: {archive_file}")

    index_file = "archive/index.json"
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            archive_index = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        archive_index = {"dates": []}
    dates = list(dict.fromkeys([date_key] + archive_index.get("dates", [])))
    archive_index = {"dates": sorted(dates, reverse=True)[:90]}
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(archive_index, f, ensure_ascii=False, indent=2)
    print(f"📋 아카이브 인덱스: {len(archive_index['dates'])}일치")


# ── 메인 ─────────────────────────────────────────────────────────────
def main():
    now      = datetime.now(KST)
    date_key = now.strftime("%Y-%m-%d")
    date_str = now.strftime("%Y-%m-%d")
    now_str  = now.strftime("%Y-%m-%d %H:%M")

    print(f"[{now.strftime('%H:%M')}] The Signal Korea 기사 생성 시작 (v2)...")

    try:
        print("📡 RSS 뉴스 수집 중...")
        raw_news = collect_news_from_rss()
        print(f"   → {len(raw_news)}건 수집됨")

        print("📚 최근 기사 제목 로드 (중복 방지)...")
        recent_titles = get_recent_titles(days=3)
        print(f"   → {len(recent_titles)}개 제목 로드됨")

        print("📊 sojaetimes 전문 인텔리전스 브리핑 로드 중...")
        sojaetimes_briefing = load_sojaetimes_briefing()

        print("✍️  Claude API로 기사 작성 중...")
        articles = generate_articles_with_claude(raw_news, recent_titles, sojaetimes_briefing)
        brief_count = sum(1 for a in articles if a.get("is_brief"))
        print(f"   → 기사 {len(articles)}건 생성됨 (속보형 {brief_count}건)")

        print("🔍 생성된 기사 중복 검사 중...")
        articles = deduplicate_articles(articles)

        # id를 배열 위치(0-based)로 정규화 — 이미지 파일명(article_{i}.jpg)과
        # id를 일치시켜, 검수 단계의 id 기반 재다운로드가 남의 이미지를 덮어쓰지 않게 한다.
        for i, a in enumerate(articles):
            a["id"] = i

        # 카테고리 분포 확인
        from collections import Counter
        cat_dist = Counter(a["category"] for a in articles)
        print(f"   → 카테고리 분포: {dict(cat_dist)}")

        print("🖼️  기사 이미지 다운로드 중...")
        articles = download_article_images(articles, date_str)

        print("📰 편집장 브리핑 + 핵심 시그널 생성 중...")
        briefing, signals = generate_editorial(articles)

        save_data(articles, briefing, signals, date_str, date_key)
        print("🎉 완료!")

        # 텔레그램 완료 알림
        cat_dist_str = ", ".join(f"{k}:{v}건" for k, v in cat_dist.items())
        title_list = "\n".join(
            f"  {i+1}. [{a.get('category','')}] {a.get('title','')}"
            for i, a in enumerate(articles)
        )
        tg_msg = (
            f"✅ <b>더 시그널 코리아 기사 생성 완료</b>\n"
            f"{now_str}\n\n"
            f"기사 {len(articles)}건 생성 (속보형 {brief_count}건):\n{title_list}\n\n"
            f"카테고리: {cat_dist_str}\n"
            f"📋 브리핑: {briefing[:80]}{'...' if len(briefing) > 80 else ''}"
        )
        send_telegram(tg_msg)

    except Exception as e:
        error_msg = f"❌ <b>더 시그널 코리아 기사 생성 오류</b>\n{now_str}\n\n{type(e).__name__}: {e}"
        print(error_msg)
        send_telegram(error_msg)
        raise


if __name__ == "__main__":
    main()
