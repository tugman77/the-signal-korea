"""
더 시그널 코리아 전문 정보수집 - GitHub Actions 연동용
4개 분야(공급망전쟁, 기술패권, 산업전략, 글로벌분석) 뉴스를 수집하고
sojaetimes/briefing_YYYYMMDD.json 으로 저장한다.

실행: python sojaetimes/collect.py
필요 환경변수(선택):
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET  — 네이버 뉴스 API (없으면 Google RSS만 사용)
"""

import feedparser
import json
import os
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# ── 네이버 뉴스 API 설정 ──────────────────────────────────────────
NAVER_CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
NAVER_NEWS_URL      = "https://openapi.naver.com/v1/search/news.json"

# 분야별 네이버 검색 키워드
NAVER_TOPICS = [
    # (분야, 키워드)
    ("공급망전쟁", "갈륨 게르마늄 수출규제"),
    ("공급망전쟁", "탄탈럼 희토류 공급망"),
    ("공급망전쟁", "중국 수출통제 소재"),
    ("공급망전쟁", "핵심광물 공급망 한국"),
    ("기술패권",   "미중 반도체 패권"),
    ("기술패권",   "AI 반도체 수출통제"),
    ("기술패권",   "CHIPS법 반도체 지원"),
    ("산업전략",   "소부장 국산화 투자"),
    ("산업전략",   "한국 산업전략 공급망"),
    ("산업전략",   "반도체 배터리 정책"),
    ("글로벌분석", "미국 EU 산업 공급망"),
    ("글로벌분석", "인도 제조업 반도체"),
    ("글로벌분석", "일본 소재 장비 전략"),
]

# 분야별 Google News RSS
GOOGLE_RSS_TOPICS = [
    ("공급망전쟁", "https://news.google.com/rss/search?q=갈륨+게르마늄+수출+규제+공급망&hl=ko&gl=KR&ceid=KR:ko"),
    ("공급망전쟁", "https://news.google.com/rss/search?q=gallium+germanium+export+control+supply+chain&hl=en&gl=US&ceid=US:en"),
    ("공급망전쟁", "https://news.google.com/rss/search?q=critical+minerals+export+ban+China&hl=en&gl=US&ceid=US:en"),
    ("기술패권",   "https://news.google.com/rss/search?q=미중+반도체+패권+수출통제&hl=ko&gl=KR&ceid=KR:ko"),
    ("기술패권",   "https://news.google.com/rss/search?q=US+China+chip+war+semiconductor+export&hl=en&gl=US&ceid=US:en"),
    ("기술패권",   "https://news.google.com/rss/search?q=CHIPS+Act+AI+semiconductor+technology&hl=en&gl=US&ceid=US:en"),
    ("산업전략",   "https://news.google.com/rss/search?q=한국+소부장+산업전략+투자&hl=ko&gl=KR&ceid=KR:ko"),
    ("산업전략",   "https://news.google.com/rss/search?q=Korea+industrial+strategy+supply+chain&hl=en&gl=US&ceid=US:en"),
    ("글로벌분석", "https://news.google.com/rss/search?q=글로벌+공급망+재편+산업&hl=ko&gl=KR&ceid=KR:ko"),
    ("글로벌분석", "https://news.google.com/rss/search?q=global+supply+chain+reshoring+manufacturing&hl=en&gl=US&ceid=US:en"),
]


def _empty_topics():
    return {t: [] for t in ["공급망전쟁", "기술패권", "산업전략", "글로벌분석"]}


def _seen_key(item):
    return item.get("link", "") or item.get("title", "")


def collect_naver(max_per_query=5) -> dict:
    """네이버 뉴스 API로 분야별 수집"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("   네이버 API 키 없음 — Google RSS만 사용")
        return _empty_topics()

    result = _empty_topics()
    seen: set = set()
    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }

    for topic, keyword in NAVER_TOPICS:
        try:
            resp = requests.get(
                NAVER_NEWS_URL,
                headers=headers,
                params={"query": keyword, "display": max_per_query, "sort": "date"},
                timeout=10,
            )
            if resp.status_code != 200:
                print(f"   네이버 API 오류 [{keyword}]: {resp.status_code}")
                continue
            items = resp.json().get("items", [])
            for item in items:
                key = item.get("link", item.get("title", ""))
                if key in seen:
                    continue
                seen.add(key)
                result[topic].append({
                    "source":    "네이버뉴스",
                    "lang":      "ko",
                    "topic":     topic,
                    "title":     item.get("title", "").replace("<b>", "").replace("</b>", ""),
                    "summary":   item.get("description", "").replace("<b>", "").replace("</b>", "")[:300],
                    "link":      item.get("link", ""),
                    "published": item.get("pubDate", ""),
                })
        except Exception as e:
            print(f"   네이버 수집 오류 [{keyword}]: {e}")

    return result


def collect_google_rss(max_per_feed=4) -> dict:
    """Google News RSS로 분야별 수집 (한국어 + 영어)"""
    result = _empty_topics()
    seen: set = set()

    for topic, url in GOOGLE_RSS_TOPICS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                key = entry.get("link", entry.get("title", ""))
                if key in seen:
                    continue
                seen.add(key)
                lang = "en" if "ceid=US:en" in url else "ko"
                result[topic].append({
                    "source":    "GoogleNews",
                    "lang":      lang,
                    "topic":     topic,
                    "title":     entry.get("title", ""),
                    "summary":   entry.get("summary", "")[:300],
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"   Google RSS 오류 [{url[:60]}]: {e}")

    return result


def merge(a: dict, b: dict) -> dict:
    """두 분야별 dict 합산 (중복 링크 제거)"""
    merged = _empty_topics()
    for topic in merged:
        seen: set = set()
        for item in a.get(topic, []) + b.get(topic, []):
            key = _seen_key(item)
            if key not in seen:
                seen.add(key)
                merged[topic].append(item)
    return merged


def main():
    now = datetime.now(KST)
    date_key = now.strftime("%Y-%m-%d")
    print(f"[signal collect] {date_key} 수집 시작")

    naver_data  = collect_naver()
    google_data = collect_google_rss()
    topics      = merge(naver_data, google_data)

    total = sum(len(v) for v in topics.values())
    print(f"총 {total}건 수집:")
    for topic, items in topics.items():
        ko = sum(1 for i in items if i["lang"] == "ko")
        en = sum(1 for i in items if i["lang"] == "en")
        print(f"  {topic}: {len(items)}건 (한{ko}/영{en})")

    briefing = {
        "date":         date_key,
        "collected_at": now.strftime("%Y-%m-%d %H:%M KST"),
        "total_count":  total,
        "topics":       topics,
    }

    os.makedirs("sojaetimes", exist_ok=True)
    out = f"sojaetimes/briefing_{date_key}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {out}")


if __name__ == "__main__":
    main()
