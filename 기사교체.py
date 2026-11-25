"""오늘 발행한 기사 한 건을 다른 주제의 새 기사로 바꾼다.

2026-11-25 대표님 지시: 범위 밖 기사(생맥주 주세)를 다른 기사를 발굴해 대체.
같은 자리(id·이미지 파일명·정적 페이지 주소)를 그대로 쓰므로 이미 나간 링크는 새 기사를 연다.

순서: 새로 수집(RSS + 네이버/구글 브리핑) → 1건 집필(기존 v2 경로, 범위 규칙 포함) → 이미지 →
편집장 브리핑 재작성 → save_data(articles.json·아카이브·정적 페이지·카드·sitemap/rss) → 토픽 원장.
검수·커밋·push는 이 스크립트 다음에 기존대로 `기사검수.py` → git으로 한다.

사용: python3 기사교체.py --index 2 [--reason "범위 밖"] [--dry]
  --dry: 새 기사를 만들어 화면에만 보여 주고 아무 파일도 쓰지 않는다.
"""
import argparse
import json
import os
import sys
from datetime import datetime

import 기사자동생성 as G

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sojaetimes"))
import collect as sj_collect  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=int, required=True, help="바꿀 기사 위치(0부터)")
    ap.add_argument("--reason", default="채널 범위 밖")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    with open(G.OUTPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    date_key = data.get("date_key")
    today = datetime.now(G.KST).strftime("%Y-%m-%d")
    if date_key != today:
        sys.exit(f"❌ articles.json 날짜({date_key})가 오늘({today})이 아니다 — 오늘 기사만 교체한다")
    articles = data["articles"]
    if not 0 <= args.index < len(articles):
        sys.exit(f"❌ index {args.index} 없음 (기사 {len(articles)}건)")
    old = articles[args.index]
    keep = [a for i, a in enumerate(articles) if i != args.index]
    print(f"🔁 교체 대상 [{args.index}] {old.get('title')} — {args.reason}")

    print("📡 자료 새로 수집...")
    raw = G.collect_news_from_rss()
    briefing = {"topics": sj_collect.merge(sj_collect.collect_naver(), sj_collect.collect_google_rss())}
    recent = G.get_recent_titles(days=G.RECENT_CONTEXT_DAYS)
    history = G.load_topic_history()
    cooldown = G.build_cooldown_block(history, date_key)
    keep_lines = "\n".join(f"  - [{a.get('category')}] {a.get('title')} (topic_key: {a.get('topic_key')})" for a in keep)
    cooldown += f"""

[오늘 기사 교체 — 반드시 준수]
오늘 이미 나간 기사 중 1건을 다른 주제로 바꾼다. 아래 유지 기사와 같은 사건·기업·소재를 다루지 않는다.
{keep_lines}
교체 대상(쓰지 않는다, 사유: {args.reason}): {old.get('title')} (topic_key: {old.get('topic_key')})
이번에는 기사 1건만 쓴다. 카테고리 비중 규칙 대신 유지 기사와 다른 카테고리를 우선 고려한다.
"""

    G.ARTICLE_COUNT = 1
    new = G.generate_articles_v2(raw, recent, briefing, cooldown)[0]
    new["id"] = args.index
    new["is_featured"] = bool(old.get("is_featured"))
    print(f"✍️  새 기사: [{new.get('category')}] {new.get('title')}")
    print(f"   요약: {new.get('summary')}")
    print(f"   출처: {[s.get('title') for s in new.get('sources', [])]}")
    if args.dry:
        print(json.dumps(new, ensure_ascii=False, indent=2)[:4000])
        return

    # 이미지 — 같은 파일명에 덮어쓴다 (download_article_images와 같은 준비 단계)
    G._used_photo_ids.clear()
    G._run_hashes.clear()
    G._load_image_history()
    G._validate_pool()
    img_path = old.get("image_url") or f"{G.IMAGES_DIR}/{date_key}_article_{args.index}.jpg"
    seed = f"{date_key}_{args.index}_{new.get('title', '')}"
    if G._download_single_image(new.get("image_keyword", ""), img_path, new.get("category", "글로벌분석"),
                                seed, new.get("title", "")):
        new["image_url"] = img_path
        G.이미지생성.mark(new, img_path in G.AI_IMAGE_PATHS)
    else:
        new["image_url"] = None
    G._save_image_history()

    articles[args.index] = new
    keep_ts = {i: a.get("timestamp") for i, a in enumerate(articles) if i != args.index}
    print("📰 편집장 브리핑 다시 작성...")
    brief, signals = G.generate_editorial(articles)
    G.save_data(articles, brief, signals, date_key, date_key)

    # save_data가 모든 기사 시각을 지금으로 덮으므로, 유지 기사는 원래 발행 시각으로 되돌린다
    if any(keep_ts.values()):
        for path in (G.OUTPUT_FILE, f"archive/{date_key}.json"):
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            for i, ts in keep_ts.items():
                if ts:
                    d["articles"][i]["timestamp"] = ts
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        import 정적페이지생성
        정적페이지생성.generate_for_date(date_key, d, 정적페이지생성.extract_style())

    # 토픽 원장 — 교체된 키는 지우고 새 키를 기록 (오늘 다른 기사가 같은 키를 쓰면 남긴다)
    old_key = (old.get("topic_key") or "").strip()
    if old_key and old_key not in {(a.get("topic_key") or "").strip() for a in articles}:
        history.pop(old_key, None)
        with open(G.TOPIC_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    G.save_topic_history([new], date_key)
    print("🎉 교체 완료 — 다음: 기사검수.py → git push")


if __name__ == "__main__":
    main()
