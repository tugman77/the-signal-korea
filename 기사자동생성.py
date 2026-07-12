"""
더 시그널 코리아 (The Signal Korea) — 자동 기사 생성 스크립트 v2
실행: python 기사자동생성.py
필요: pip install anthropic requests feedparser

업그레이드 내역 (v2):
  - 이미지 우선순위: Unsplash → Pexels → Pixabay → 큐레이션 풀 → picsum
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
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "여기에_API키_입력")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")   # 선택 — 있으면 사용
PEXELS_API_KEY      = os.environ.get("PEXELS_API_KEY", "")        # 선택 — 있으면 사용
PIXABAY_API_KEY     = os.environ.get("PIXABAY_API_KEY", "")       # 선택 — 있으면 사용

OUTPUT_FILE = "articles.json"
IMAGES_DIR  = "images"

# ── 카테고리별 큐레이션 이미지 풀 (모든 API 실패 시 사용) ──
CURATED_IMAGE_POOL = {
    "공급망전쟁": [
        "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800&h=450&fit=crop",
        "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800&h=450&fit=crop",
        "https://images.unsplash.com/photo-1578575437130-527eed3abbec?w=800&h=450&fit=crop",
    ],
    "기술패권": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&h=450&fit=crop",
        "https://images.unsplash.com/photo-1563770660941-20978e870e26?w=800&h=450&fit=crop",
        "https://images.unsplash.com/photo-1601597111158-2fceff292cdc?w=800&h=450&fit=crop",
    ],
    "산업전략": [
        "https://images.unsplash.com/photo-1565514020179-026b92b84bb6?w=800&h=450&fit=crop",
        "https://images.unsplash.com/photo-1504328345606-18bbc8c9d7d1?w=800&h=450&fit=crop",
    ],
    "글로벌분석": [
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&h=450&fit=crop",
        "https://images.unsplash.com/photo-1524522173746-f628baad3644?w=800&h=450&fit=crop",
    ],
}

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


# ── Claude API로 기사 생성 ──────────────────────────────────────────
def generate_articles_with_claude(raw_news_list, recent_titles):
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

{news_section}

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
- SEO용 image_keyword: "gallium export restriction Korea", "tantalum supply chain" 등 구체적 소재명 포함 영문 2~3단어

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
                                "image_keyword": {"type": "string"},
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


# ── 이미지 다운로드 (우선순위: Unsplash → Pexels → Pixabay → 큐레이션 → picsum) ──
def try_download(url, path, min_size=2000, timeout=20):
    """단일 URL 다운로드 시도. 성공 시 True."""
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True,
                            headers={"User-Agent": "TheSignalKorea/2.0"})
        if resp.status_code == 200 and len(resp.content) >= min_size:
            with open(path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        print(f"      다운로드 실패 ({url[:50]}...): {e}")
    return False


def fetch_unsplash(keyword, path):
    if not UNSPLASH_ACCESS_KEY:
        return False
    try:
        r = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": keyword, "orientation": "landscape", "per_page": 1},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=15
        )
        if r.status_code == 200:
            img_url = r.json().get("urls", {}).get("regular", "")
            if img_url:
                return try_download(img_url, path)
    except Exception as e:
        print(f"      Unsplash 오류: {e}")
    return False


def fetch_pexels(keyword, path):
    if not PEXELS_API_KEY:
        return False
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": keyword, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": PEXELS_API_KEY},
            timeout=15
        )
        if r.status_code == 200:
            photos = r.json().get("photos", [])
            if photos:
                img_url = photos[0].get("src", {}).get("large", "")
                if img_url:
                    return try_download(img_url, path)
    except Exception as e:
        print(f"      Pexels 오류: {e}")
    return False


def fetch_pixabay(keyword, path):
    if not PIXABAY_API_KEY:
        return False
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={"key": PIXABAY_API_KEY, "q": keyword,
                    "image_type": "photo", "orientation": "horizontal", "per_page": 3},
            timeout=15
        )
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                img_url = hits[0].get("webformatURL", "")
                if img_url:
                    return try_download(img_url, path)
    except Exception as e:
        print(f"      Pixabay 오류: {e}")
    return False


def fetch_curated(category, article_idx, path):
    pool = CURATED_IMAGE_POOL.get(category, CURATED_IMAGE_POOL["글로벌분석"])
    idx = article_idx % len(pool)
    return try_download(pool[idx], path)


def fetch_picsum(keyword, path):
    seed = hashlib.md5(keyword.encode()).hexdigest()[:8]
    url = f"https://picsum.photos/seed/{seed}/800/450"
    return try_download(url, path, min_size=1000)


def download_article_images(articles, date_str):
    os.makedirs(IMAGES_DIR, exist_ok=True)

    for i, article in enumerate(articles):
        keyword  = article.get("image_keyword", "technology industry Korea")
        category = article.get("category", "글로벌분석")
        img_path = f"{IMAGES_DIR}/{date_str}_article_{i}.jpg"
        saved    = False

        print(f"   이미지 [{i}] 키워드: {keyword}")

        # 1순위: Unsplash API
        if not saved:
            saved = fetch_unsplash(keyword, img_path)
            if saved: print(f"      → Unsplash 저장: {img_path}")

        # 2순위: Pexels API
        if not saved:
            saved = fetch_pexels(keyword, img_path)
            if saved: print(f"      → Pexels 저장: {img_path}")

        # 3순위: Pixabay API
        if not saved:
            saved = fetch_pixabay(keyword, img_path)
            if saved: print(f"      → Pixabay 저장: {img_path}")

        # 4순위: 큐레이션 풀 (카테고리별 고정 URL)
        if not saved:
            saved = fetch_curated(category, i, img_path)
            if saved: print(f"      → 큐레이션 풀 저장: {img_path}")

        # 5순위: picsum (최후 수단)
        if not saved:
            saved = fetch_picsum(keyword, img_path)
            if saved: print(f"      → picsum 저장: {img_path}")

        if saved:
            article["image_url"] = img_path
        else:
            article["image_url"] = None
            print(f"      → 이미지 모두 실패 [{keyword}]")

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

    print(f"[{now.strftime('%H:%M')}] The Signal Korea 기사 생성 시작 (v2)...")

    print("📡 RSS 뉴스 수집 중...")
    raw_news = collect_news_from_rss()
    print(f"   → {len(raw_news)}건 수집됨")

    print("📚 최근 기사 제목 로드 (중복 방지)...")
    recent_titles = get_recent_titles(days=3)
    print(f"   → {len(recent_titles)}개 제목 로드됨")

    print("✍️  Claude API로 기사 작성 중...")
    articles = generate_articles_with_claude(raw_news, recent_titles)
    brief_count = sum(1 for a in articles if a.get("is_brief"))
    print(f"   → 기사 {len(articles)}건 생성됨 (속보형 {brief_count}건)")

    print("🔍 생성된 기사 중복 검사 중...")
    articles = deduplicate_articles(articles)

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


if __name__ == "__main__":
    main()
