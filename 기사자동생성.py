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

from __future__ import annotations  # 로컬 Python 3.9에서 `str | None` 등 어노테이션 허용 (지연 평가)

import anthropic
import llm_backend  # 구독코인(로컬 Claude Code) / API코인(anthropic SDK) 전환
import 이미지필터    # 이미지 키워드 오매칭(예: wafer → 과자) 방지 필터
import 이미지소스    # 외부 이미지 소스 API (Unsplash/Pexels/Pixabay)
import 이미지풀      # 카테고리별 큐레이션 풀 (로컬 self-host + Unsplash hotlink)
import feedparser
import json
import os
import requests
import hashlib
import random
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "여기에_API키_입력")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")   # 선택 — 있으면 사용
PEXELS_API_KEY      = os.environ.get("PEXELS_API_KEY", "")        # 선택 — 있으면 사용
PIXABAY_API_KEY     = os.environ.get("PIXABAY_API_KEY", "")       # 선택 — 있으면 사용
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")       # 관리자 알림용(비공개)
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")    # 공개 채널 발행용(@username 또는 -100…)

OUTPUT_FILE = "articles.json"
SITE_URL    = "https://www.thesignalkorea.co.kr"  # SEO/RSS 절대경로 기준
IMAGES_DIR  = "images"
IMAGE_HISTORY_FILE = "image_history.json"  # 날짜 간 photo-ID·MD5 이력 (run 간 재사용 방지)
TOPIC_HISTORY_FILE = "scripts/topic_history.json"  # 토픽키 → 마지막 발행일 (반복 주제 쿨다운). 워크플로 git add의 scripts/ 에 포함돼 run 간 유지된다.
TOPIC_COOLDOWN_DAYS = 7                     # 이 기간 내 다룬 토픽은 '새 전개' 있을 때만 재발행
RECENT_CONTEXT_DAYS = 10                    # 프롬프트에 넣을 최근 발행 기사 창(제목+요약)

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
# 풀 목록은 이미지풀.py 한 곳에서만 관리한다 (소재타임스와 동일 구조).

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


# ── 공개 텔레그램 채널 발행 (독자용) ──────────────────────────────
# 관리자 알림(send_telegram)과 분리. TELEGRAM_CHANNEL_ID 설정 시에만 동작.
_CAT_EMOJI = {
    "기술패권": "🔴", "공급망전쟁": "🟠", "산업전략": "🟢", "글로벌분석": "🔵",
}


def _tg_escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_channel_message(articles, date_key, now) -> str:
    date_label = now.strftime("%Y년 %m월 %d일")
    lines = [f"📡 <b>THE SIGNAL KOREA</b>",
             f"{date_label} · 오늘의 시그널 {len(articles)}건", ""]
    for a in articles:
        emoji = _CAT_EMOJI.get(a.get("category", ""), "📌")
        title = _tg_escape(a.get("title", ""))
        cat = _tg_escape(a.get("category", ""))
        summary = _tg_escape((a.get("summary", "") or "").strip())
        if len(summary) > 110:
            summary = summary[:110].rstrip() + "…"
        link = f"{SITE_URL}/article.html?date={date_key}&id={a.get('id', 0)}"
        brief = " ⚡속보" if a.get("is_brief") else ""
        lines.append(f"{emoji} <b>[{cat}]{brief}</b> {title}")
        if summary:
            lines.append(f"<i>{summary}</i>")
        lines.append(f'<a href="{link}">▸ 5단계 분석 보기</a>')
        lines.append("")
    lines.append(f'🔗 <a href="{SITE_URL}/">전체 기사 보기</a>')
    lines.append("#공급망전쟁 #기술패권 #반도체 #산업분석 #투자")
    return "\n".join(lines)


def post_to_channel(articles, date_key, now) -> bool:
    """오늘 발행분을 공개 채널에 독자용 다이제스트로 발행. 채널 미설정 시 skip."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("[채널 미설정] TELEGRAM_CHANNEL_ID 없음 — 채널 발행 건너뜀")
        return False
    if not articles:
        return False
    text = build_channel_message(articles, date_key, now)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        if resp.ok:
            print(f"📣 채널 발행 완료 — {len(articles)}건")
            return True
        print(f"❌ 채널 발행 실패 {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"채널 발행 오류: {e}")
        return False


def send_cards_to_admin(articles, date_key) -> bool:
    """생성된 카드뉴스 이미지를 관리자 채팅으로 전송 — X·스레드에 원탭 리포스트용.
    각 카드에 붙여넣기용 캡션(제목+링크+해시태그) 첨부. TELEGRAM_CHAT_ID 필요, 카드 파일 없으면 skip."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    photos = [(i, a, f"cards/{date_key}-{i}.png")
              for i, a in enumerate(articles)
              if os.path.exists(f"cards/{date_key}-{i}.png")]
    if not photos:
        print("[카드전송] 카드 이미지 없음 — skip")
        return False
    send_telegram(f"🎴 <b>오늘의 카드뉴스 {len(photos)}장</b>\n아래 이미지를 저장해 X·스레드에 올리세요 (캡션은 복사용으로 함께 보냅니다)")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    sent = 0
    for i, a, path in photos:
        cat = a.get("category", "")
        emoji = _CAT_EMOJI.get(cat, "📌")
        link = f"{SITE_URL}/news/{date_key}-{i}.html"
        caption = (f"{emoji} [{cat}] {a.get('title','')}\n\n"
                   f"▸ {link}\n"
                   f"#{cat} #공급망 #반도체 #산업분석 #투자")
        try:
            with open(path, "rb") as fp:
                resp = requests.post(url,
                                     data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                                     files={"photo": fp}, timeout=30)
            if resp.ok:
                sent += 1
            else:
                print(f"❌ 카드 전송 실패 {i}: {resp.status_code} {resp.text[:120]}")
        except Exception as e:
            print(f"카드 전송 오류 {i}: {e}")
    print(f"🎴 관리자에게 카드 {sent}/{len(photos)}장 전송")
    return sent > 0


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


# ── 최근 발행 기사 컨텍스트 (제목+요약) 추출 (중복 주제 방지) ──────
def get_recent_titles(days=RECENT_CONTEXT_DAYS):
    """최근 `days`일 발행 기사의 '제목 — 요약' 리스트 반환 (중복 제거).
    제목만이 아니라 요약까지 넣어 '단어만 바꾼 같은 토픽'을 모델이 인지하게 한다."""
    items, seen = [], set()

    def _add(arts):
        for a in arts:
            t = (a.get("title") or "").strip()
            if not t or t in seen:
                continue
            seen.add(t)
            s = (a.get("summary") or "").strip()
            items.append(f"{t} — {s[:60]}" if s else t)

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            _add(json.load(f).get("articles", []))
    except Exception:
        pass
    try:
        with open("archive/index.json", "r", encoding="utf-8") as f:
            idx = json.load(f)
        for dk in (idx.get("dates", []))[:days]:
            try:
                with open(f"archive/{dk}.json", "r", encoding="utf-8") as f:
                    _add(json.load(f).get("articles", []))
            except Exception:
                pass
    except Exception:
        pass
    return items


# ── 토픽 원장 (반복 주제 쿨다운) ──────────────────────────────────
def load_topic_history():
    """topic_history.json → {topic_key: 'YYYY-MM-DD'} 로드. 없으면 빈 dict."""
    try:
        with open(TOPIC_HISTORY_FILE, "r", encoding="utf-8") as f:
            h = json.load(f)
        return h if isinstance(h, dict) else {}
    except Exception:
        return {}


def build_cooldown_block(history, today_str, days=TOPIC_COOLDOWN_DAYS):
    """최근 `days`일 내 다룬 토픽을 '경과일'과 함께 프롬프트 블록 텍스트로 만든다."""
    from datetime import date
    try:
        today = date.fromisoformat(today_str)
    except Exception:
        return ""
    rows = []
    for key, last in history.items():
        try:
            gap = (today - date.fromisoformat(last)).days
        except Exception:
            continue
        if 0 <= gap <= days:
            rows.append((gap, key))
    if not rows:
        return ""
    rows.sort()
    lines = "\n".join(
        f"  - {key} ({'오늘' if g == 0 else f'{g}일 전'} 다룸)" for g, key in rows
    )
    return f"""
[최근 다룬 토픽 — 쿨다운 {days}일]
아래 토픽은 최근 {days}일 내 이미 발행했습니다. **"새로운 전개(신규 수치·사건·정책 변화)"가 있을 때만** 재발행하고,
그 변화점을 제목과 FACT 첫 단락에 반드시 명시하세요. 새 전개가 없으면 이 토픽은 건너뛰고 다른 주제를 고르세요.
{lines}
"""


def save_topic_history(articles, date_str):
    """생성 확정된 기사들의 topic_key를 오늘 날짜로 기록. 오래된(30일↑) 항목은 정리."""
    from datetime import date
    history = load_topic_history()
    for a in articles:
        key = (a.get("topic_key") or "").strip()
        if key:
            history[key] = date_str
    try:
        today = date.fromisoformat(date_str)
        history = {k: v for k, v in history.items()
                   if _within_days(v, today, 30)}
    except Exception:
        pass
    try:
        with open(TOPIC_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"   ⚠️ topic_history 저장 실패: {e}")


def _within_days(date_iso, today, n):
    from datetime import date
    try:
        return (today - date.fromisoformat(date_iso)).days <= n
    except Exception:
        return False


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
def generate_articles_with_claude(raw_news_list, recent_titles, sojaetimes_briefing=None, cooldown_block=""):
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
        recent_list = "\n".join(f"  - {t}" for t in recent_titles[:40])
        recent_block = f"""
[최근 {RECENT_CONTEXT_DAYS}일 발행 기사 — 재탕 금지]
아래는 최근 발행분(제목 — 요약)입니다. 표현·수치를 바꿔도 **같은 사건·같은 결론**이면 재탕입니다.
동일 토픽은 새로운 전개가 있을 때만, 그 변화점을 앞세워 다루세요:
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
{cooldown_block}

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
- topic_key: 위 스키마 설명대로 사건 단위 정규화 키를 반드시 부여. 같은 사건이면 표현이 달라도 동일 키. 5개 기사의 topic_key는 서로 달라야 하며, 위 '쿨다운' 목록의 키와 겹치면 새 전개가 없는 한 그 주제를 피할 것.
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

    request_params = dict(
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
                                "topic_key":     {"type": "string", "description": "이 기사의 핵심 사건을 나타내는 정규화 토픽키. 핵심 엔티티+사건을 한글 2~4단어로 하이픈 연결(예: '고려아연-갈륨-국내생산', '미중-AI칩-수출통제', '중국-헬륨-수출통제'). 표현이 달라도 같은 사건이면 반드시 같은 키를 쓸 것 — 날짜 간 중복 판정에 쓰인다."},
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
                            "required": ["id","topic_key","category","tag_type","title","summary","is_brief",
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
    )

    # ── LLM 호출: 구독코인(Claude Code) vs API코인(anthropic SDK) ──
    if llm_backend.using_subscription():
        articles = llm_backend.call_tool(request_params, "save_articles")["articles"]
    else:
        with client.messages.stream(**request_params) as stream:
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
        request_params = dict(
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
        # ── LLM 호출: 구독코인 vs API코인 ──
        if llm_backend.using_subscription():
            data = llm_backend.call_tool(request_params, "save_editorial")
            briefing, signals = data["briefing"], data["signals"]
        else:
            response = client.messages.create(**request_params)
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
_run_hashes: set        = set()   # 이번 실행에서만 저장된 MD5 (큐레이션 풀 전용 판정)

# ⚠️ 큐레이션 풀은 영구 해시 대조에서 제외한다 (2026-08-02 소재타임스에서 이식).
# 풀 URL은 고정이라 바이트가 매일 같다 → 영구 히스토리에 넣는 순간 그 photo-ID가 영영 죽는다.
# 이 채널도 이식 시점에 34장 중 18장(52%)이 이미 그렇게 죽어 picsum 폴백 직전이었다.
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
    """풀 cross-category 중복 감지 (이미지풀.py 위임)"""
    이미지풀.validate()


def _pick_pool_entry(category: str, seed_str: str):
    """풀에서 LRU로 한 항목 선택 → 항목 dict 반환 (없으면 None)"""
    entry = 이미지풀.pick(category, seed_str, _used_photo_ids, _photo_id_last_used)
    if entry:
        _used_photo_ids.add(entry["id"])
    return entry


def _record_photo_id(photo_id: str):
    """실제 저장에 사용된 photo-ID의 마지막 사용 날짜를 오늘로 기록."""
    if photo_id:
        _photo_id_last_used[photo_id] = datetime.now(KST).strftime("%Y-%m-%d")


# 외부 소스 검색은 이미지소스.py로 이관했다 (오매칭 필터가 붙은 공용 구현).
# 아래 두 이름은 기존 호출부 호환용 얇은 위임이다.

def _fetch_pexels(keyword: str) -> str | None:
    return 이미지소스.fetch_pexels(keyword)


def _fetch_pixabay(keyword: str) -> str | None:
    return 이미지소스.fetch_pixabay(keyword)


def _download_single_image(keyword: str, img_path: str, category: str, seed_str: str) -> bool:
    """소스 우선순위(Unsplash count=10 → Pexels → Pixabay → 풀 → picsum)로 시도.
    MD5 중복이면 저장하지 않고 다음 소스로 넘어간다."""
    global _downloaded_hashes
    # 검색 전 1차 방어 — 중의적 키워드(wafer/chip/foil…)에 업계 한정어를 붙인다
    refined = 이미지필터.refine_keyword(keyword, category)
    if refined != keyword:
        print(f"      → 키워드 보정: '{keyword}' → '{refined}'")
        keyword = refined
    seed = hashlib.md5(keyword.encode()).hexdigest()[:8]

    # 소스 목록은 이미지소스.py가 키 등록 상태를 보고 결정한다
    order: list[str] = list(이미지소스.available_sources())
    order += ["unsplash_pool"] * max(이미지풀.size(category), 8)
    order.append("picsum")

    pool_try = 0
    unsplash_candidates: list[str] = []  # count=10 후보 캐시
    for source in order:
        chosen_pid = None
        try:
            if source == "unsplash_api":
                # 후보를 한 번에 받아 두고 하나씩 소비 — 중복 거부돼도 같은 소스에서 이어간다
                if not unsplash_candidates:
                    unsplash_candidates = 이미지소스.fetch_unsplash_candidates(keyword)
                img_url = unsplash_candidates.pop(0) if unsplash_candidates else ""
                if not img_url:
                    continue
                # 아직 후보가 남아있으면 이 소스를 한 번 더 시도할 수 있게 재삽입
                if unsplash_candidates:
                    order.insert(order.index(source) + 1, "unsplash_api")
            elif source in 이미지소스.FETCHERS:
                img_url = 이미지소스.fetch(source, keyword)
                if not img_url:
                    continue
            elif source == "unsplash_pool":
                entry = _pick_pool_entry(category, f"{seed_str}_{pool_try}")
                pool_try += 1
                if not entry:
                    continue
                chosen_pid = entry["id"]
                content = 이미지풀.read_bytes(entry)   # 로컬은 파일 읽기, 원격은 HTTP
                if not content:
                    continue
                img_url = entry["ref"]
            else:
                img_url = f"https://picsum.photos/seed/{seed}/800/450"

            is_pool = (source == "unsplash_pool")
            if not is_pool:
                resp = requests.get(img_url, timeout=30, allow_redirects=True,
                                    headers={"User-Agent": "TheSignalKorea/3.0"})
                if resp.status_code != 200 or len(resp.content) < 1000:
                    continue
                content = resp.content

            # 외부 소스는 과거 날짜까지, 큐레이션 풀은 이번 실행만 대조 — 위 주석 참조
            img_hash = hashlib.md5(content).hexdigest()
            if img_hash in (_run_hashes if is_pool else _downloaded_hashes):
                scope = "오늘 이미 사용" if is_pool else "과거 사용"
                print(f"      → 중복 이미지 [{source}] md5={img_hash[:8]} ({scope}), 다음 후보 시도...")
                continue

            _run_hashes.add(img_hash)
            if not is_pool:
                # 풀 해시를 영구 히스토리에 넣으면 그 photo-ID가 영영 죽는다
                _downloaded_hashes.add(img_hash)
            _record_photo_id(chosen_pid)  # 풀 이미지일 때만 사용 날짜 기록
            with open(img_path, "wb") as f:
                f.write(content)
            print(f"      → 이미지 저장: {img_path} [{category}] ({source})")
            return True

        except Exception as e:
            print(f"      → 이미지 오류 [{source}]: {e}")

    return False


# ── 수동 검수 기사 병합 ─────────────────────────────
# 300_콘텐츠공장에서 원천자료 → 지식카드 → 브리프 → 검수를 거친 원고를
# 자동 생성분과 함께 발행하기 위한 통로. 이 통로가 없으면 손으로 넣은 기사는
# 다음 실행 때 save_data()의 덮어쓰기로 사라진다.
#
# 사용법: manual/ 에 기사 JSON 1건당 파일 1개를 둔다. 발행되면 manual/발행완료/로 옮긴다.
#         특정 날짜에 내보내려면 JSON에 "발행일": "YYYY-MM-DD" 를 넣는다(없으면 다음 실행에 발행).
#         본문 구조는 fact / meaning / winner / loser / action 배열이다.
MANUAL_DIR      = "manual"
MANUAL_DONE_DIR = os.path.join(MANUAL_DIR, "발행완료")


def load_manual_articles(date_key: str):
    """manual/*.json 을 읽어 (기사 리스트, 소비한 파일 경로) 반환."""
    if not os.path.isdir(MANUAL_DIR):
        return [], []

    articles, used = [], []
    names = sorted(n for n in os.listdir(MANUAL_DIR) if n.endswith(".json"))
    for name in names:
        path = os.path.join(MANUAL_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                item = json.load(f)
        except Exception as e:
            print(f"   ⚠️  수동 기사 읽기 실패 [{name}]: {e}")
            continue

        want = item.pop("발행일", None)
        if want and want != date_key:
            print(f"   ⏭️  {name} — 발행일 {want}, 오늘 아님")
            continue

        missing = [k for k in ("title", "summary", "fact") if not item.get(k)]
        if missing:
            print(f"   ⚠️  {name} — 필수 항목 없음: {missing}. 건너뜀")
            continue

        item.setdefault("category", "공급망전쟁")
        item.setdefault("tag_type", "tag-supply")
        item.setdefault("is_brief", False)
        item.setdefault("is_featured", False)
        item.setdefault("topic_key", os.path.splitext(name)[0])
        for key in ("meaning", "winner", "loser", "action"):
            item.setdefault(key, [])
        articles.append(item)
        used.append(path)
        print(f"   ✅ {name} — {item.get('title', '')[:40]}")

    return articles, used


def archive_manual_files(paths):
    """발행된 수동 기사 파일을 발행완료/로 옮긴다. 안 옮기면 매일 재발행된다."""
    if not paths:
        return
    os.makedirs(MANUAL_DONE_DIR, exist_ok=True)
    for path in paths:
        try:
            os.replace(path, os.path.join(MANUAL_DONE_DIR, os.path.basename(path)))
        except Exception as e:
            print(f"   ⚠️  수동 기사 이동 실패 [{path}]: {e}")
    print(f"   📦 수동 기사 {len(paths)}건 → {MANUAL_DONE_DIR}/")


def download_article_images(articles, date_str):
    """각 기사 이미지 다운로드 → images/YYYY-MM-DD_article_N.jpg
    _used_photo_ids만 run 단위로 초기화, _downloaded_hashes·_photo_id_last_used는
    image_history.json에서 로드해 날짜 간 재사용을 방지한다."""
    global _used_photo_ids
    _used_photo_ids.clear()
    _run_hashes.clear()
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
def _xml_escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def generate_seo_files(articles, date_key, now):
    """sitemap.xml + rss.xml 생성 — 검색엔진 크롤링·구독(뉴스레터/구글뉴스) 경로 확보.
    매일 발행분과 함께 자동 갱신된다. 순수 파일 생성(추가 API 호출 없음)."""
    static_pages = ["", "category.html", "search.html", "about.html",
                    "advertising.html", "privacy.html", "terms.html"]
    lastmod = now.strftime("%Y-%m-%d")

    # ── 아카이브 날짜별 기사 URL 수집 (사이트맵용) ──
    date_articles = [(date_key, articles)]
    try:
        with open("archive/index.json", "r", encoding="utf-8") as f:
            dates = json.load(f).get("dates", [])
    except (FileNotFoundError, json.JSONDecodeError):
        dates = [date_key]
    for dk in dates:
        if dk == date_key:
            continue
        try:
            with open(f"archive/{dk}.json", "r", encoding="utf-8") as f:
                date_articles.append((dk, json.load(f).get("articles", [])))
        except (FileNotFoundError, json.JSONDecodeError):
            continue

    # ── sitemap.xml ──
    urls = []
    for p in static_pages:
        loc = f"{SITE_URL}/{p}" if p else f"{SITE_URL}/"
        pr = "1.0" if p == "" else "0.6"
        urls.append(f"  <url><loc>{_xml_escape(loc)}</loc>"
                    f"<lastmod>{lastmod}</lastmod>"
                    f"<changefreq>daily</changefreq><priority>{pr}</priority></url>")
    # 기사 URL은 정적 페이지(news/YYYY-MM-DD-N.html)를 가리킨다.
    # article.html?date=..&id=.. 는 본문이 JS로만 그려져 크롤러에겐 빈 페이지다.
    for dk, arts in date_articles:
        for i, a in enumerate(arts):
            loc = f"{SITE_URL}/news/{dk}-{i}.html"
            urls.append(f"  <url><loc>{_xml_escape(loc)}</loc>"
                        f"<lastmod>{dk}</lastmod>"
                        f"<changefreq>monthly</changefreq><priority>0.8</priority></url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(urls) + "\n</urlset>\n")
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap)
    print(f"🗺️  sitemap.xml 저장 — URL {len(urls)}개")

    # ── rss.xml (최신 30개) ──
    items = []
    for dk, arts in date_articles:
        for i, a in enumerate(arts):
            items.append((dk, i, a))
    items.sort(key=lambda x: x[0], reverse=True)
    rss_items = []
    for dk, i, a in items[:30]:
        link = f"{SITE_URL}/news/{dk}-{i}.html"
        pub = datetime.strptime(dk, "%Y-%m-%d").replace(tzinfo=KST)
        rss_items.append(
            "    <item>\n"
            f"      <title>{_xml_escape(a.get('title', ''))}</title>\n"
            f"      <link>{_xml_escape(link)}</link>\n"
            f"      <guid isPermaLink=\"true\">{_xml_escape(link)}</guid>\n"
            f"      <category>{_xml_escape(a.get('category', ''))}</category>\n"
            f"      <description>{_xml_escape(a.get('summary', ''))}</description>\n"
            f"      <pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S %z')}</pubDate>\n"
            "    </item>")
    rss = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
           '  <channel>\n'
           '    <title>THE SIGNAL KOREA — 한국 산업 인텔리전스</title>\n'
           f'    <link>{SITE_URL}/</link>\n'
           f'    <atom:link href="{SITE_URL}/rss.xml" rel="self" type="application/rss+xml" />\n'
           '    <description>글로벌 기술·산업 패권 뉴스를 분석해 한국 산업의 승자·패자·액션을 짚는 인텔리전스 미디어</description>\n'
           '    <language>ko-KR</language>\n'
           f'    <lastBuildDate>{now.strftime("%a, %d %b %Y %H:%M:%S %z")}</lastBuildDate>\n'
           + "\n".join(rss_items) + "\n  </channel>\n</rss>\n")
    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"📡 rss.xml 저장 — 아이템 {len(rss_items)}개")


def save_data(articles, briefing, signals, date_str, date_key):
    now = datetime.now(KST)
    data = {
        "generated_at":    now.strftime("%Y년 %m월 %d일 %H:%M"),
        "date_str":        now.strftime("%Y년 %m월 %d일"),
        "date_key":        date_key,   # 프런트가 오늘 기사의 정적 페이지 경로를 만들 때 사용
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

    # 정적 기사 페이지 생성 — 크롤러가 읽는 정본(본문 포함 HTML).
    # article.html은 JS 렌더라 소스에 본문이 없어 색인·애드센스 심사에서 불리하다.
    try:
        import 정적페이지생성
        n = 정적페이지생성.generate_for_date(
            date_key, data, 정적페이지생성.extract_style())
        print(f"🏗️  정적 기사 페이지 {n}건 생성 — news/{date_key}-*.html")
    except Exception as e:
        print(f"⚠️ 정적 페이지 생성 실패(발행에는 영향 없음): {type(e).__name__}: {e}")

    # 스레드/X용 카드뉴스 이미지 생성 (cards/YYYY-MM-DD-N.png)
    try:
        import 카드뉴스생성
        cn = 카드뉴스생성.generate_for_date(date_key, data)
        print(f"🎴 카드뉴스 {cn}건 생성 — cards/{date_key}-*.png")
    except Exception as e:
        print(f"⚠️ 카드뉴스 생성 실패(발행에는 영향 없음): {type(e).__name__}: {e}")

    # SEO/구독 파일 갱신 (sitemap·rss)
    try:
        generate_seo_files(articles, date_key, now)
    except Exception as e:
        print(f"⚠️ SEO 파일 생성 실패(발행에는 영향 없음): {type(e).__name__}: {e}")


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

        print(f"📚 최근 {RECENT_CONTEXT_DAYS}일 발행 기사 로드 (중복 방지)...")
        recent_titles = get_recent_titles(days=RECENT_CONTEXT_DAYS)
        print(f"   → {len(recent_titles)}건 로드됨")

        print(f"🗂️  토픽 원장 로드 (쿨다운 {TOPIC_COOLDOWN_DAYS}일)...")
        topic_history = load_topic_history()
        cooldown_block = build_cooldown_block(topic_history, date_key)
        _today = datetime.fromisoformat(date_key).date()
        cooldown_keys = {k for k, v in topic_history.items()
                         if _within_days(v, _today, TOPIC_COOLDOWN_DAYS)}
        print(f"   → 쿨다운 토픽 {len(cooldown_keys)}개")

        print("📊 sojaetimes 전문 인텔리전스 브리핑 로드 중...")
        sojaetimes_briefing = load_sojaetimes_briefing()

        print("✍️  Claude API로 기사 작성 중...")
        articles = generate_articles_with_claude(raw_news, recent_titles, sojaetimes_briefing, cooldown_block)
        brief_count = sum(1 for a in articles if a.get("is_brief"))
        print(f"   → 기사 {len(articles)}건 생성됨 (속보형 {brief_count}건)")

        print("🔍 생성된 기사 중복 검사 중...")
        articles = deduplicate_articles(articles)

        # 쿨다운 토픽 재등장 모니터링 (프롬프트가 새 전개를 이유로 허용한 경우 포함 — 로그만)
        repeats = [a.get("topic_key") for a in articles if a.get("topic_key") in cooldown_keys]
        if repeats:
            print(f"   ⚠️ 쿨다운({TOPIC_COOLDOWN_DAYS}일) 내 토픽 재등장: {repeats} — 새 전개 반영분인지 확인 권장")

        # 수동 검수 기사 병합 (300_콘텐츠공장 → 채널)
        # 자동 생성분의 중복 검사를 마친 뒤에 붙인다. 검수를 이미 통과한 원고이므로
        # 중복·쿨다운 판정 대상으로 삼지 않고, 이미지·SEO·아카이브는 동일하게 태운다.
        print("📝 수동 검수 기사 확인 중...")
        manual_articles, manual_files = load_manual_articles(date_key)
        if manual_articles:
            articles = articles + manual_articles
            print(f"   → 수동 기사 {len(manual_articles)}건 병합 (총 {len(articles)}건)")
        else:
            print("   → 없음")

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
        save_topic_history(articles, date_key)

        # 발행된 수동 기사 파일 회수 — save_data 성공 후에만 옮긴다
        archive_manual_files(manual_files)
        print("🎉 완료!")

        # 공개 텔레그램 채널 발행 (독자용 다이제스트, 채널 미설정 시 자동 skip)
        post_to_channel(articles, date_key, now)

        # 카드뉴스 이미지를 관리자에게 전송 (X·스레드 리포스트용)
        send_cards_to_admin(articles, date_key)

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
