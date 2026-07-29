#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정적 기사 페이지 생성 — news/YYYY-MM-DD-N.html

article.html은 archive/*.json을 fetch로 읽어 그리는 클라이언트 렌더링이라,
크롤러가 받는 HTML에는 기사 본문이 한 줄도 없다. 검색 색인·애드센스 심사가
모두 이 HTML을 보므로, 발행할 때마다 본문이 통째로 들어간 정적 페이지를
같이 떨궈 크롤러용 정본으로 삼는다.

디자인은 article.html의 <style> 블록을 그대로 추출해 쓰므로, article.html의
CSS를 고치면 다음 발행분부터 자동으로 따라온다(중복 관리 불필요).

사용:
    python 정적페이지생성.py            # 전체 아카이브 재생성(백필)
    python 정적페이지생성.py --date 2026-07-29   # 특정 날짜만
"""

import argparse
import html
import json
import os
import re
import sys
from urllib.parse import quote
from datetime import datetime

SITE_URL = "https://www.thesignalkorea.co.kr"
OUT_DIR = "news"
ARCHIVE_DIR = "archive"
BASE = "../"  # news/ 기준 저장소 루트 상대경로

CATS = {
    "기술패권":   ("tag-hegemony", "#fee2e2", "#b91c1c"),
    "공급망전쟁": ("tag-supply",   "#fef3c7", "#b45309"),
    "산업전략":   ("tag-strategy", "#dcfce7", "#15803d"),
    "글로벌분석": ("tag-global",   "#dbeafe", "#1d4ed8"),
}

# (필드명, 영문 라벨, 한글 라벨, 섹션 클래스)
FRAMES = [
    ("fact",    "FACT",    "사실",        "frame-fact"),
    ("meaning", "MEANING", "의미",        "frame-meaning"),
    ("winner",  "WINNER",  "승자",        "frame-winner"),
    ("loser",   "LOSER",   "패자",        "frame-loser"),
    ("action",  "ACTION",  "한국의 준비", "frame-action"),
]
STEP_NUMS = ["①", "②", "③", "④", "⑤"]

BRIEF_NOTE = ("이 기사는 속보 포맷입니다. 핵심 사실(FACT)과 대응 전략(ACTION)만 "
              "빠르게 전달하며, 심층 분석(MEANING·WINNER·LOSER)은 주력 분석 기사에서 다룹니다.")


def article_path(date_key: str, idx: int) -> str:
    """정적 기사 파일의 저장소 루트 기준 경로."""
    return f"{OUT_DIR}/{date_key}-{idx}.html"


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def get_cat(article: dict):
    return CATS.get(article.get("category", ""), CATS["글로벌분석"])


def extract_style(path="article.html") -> str:
    """article.html의 <style>...</style>을 통째로 가져온다 — 디자인 단일 소스 유지."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            m = re.search(r"<style>.*?</style>", f.read(), re.S)
            return m.group(0) if m else ""
    except FileNotFoundError:
        return ""


def paras(value) -> list:
    """fact/meaning/... 필드를 단락 리스트로 정규화 (문자열이면 개행 분리)."""
    if not value:
        return []
    raw = value if isinstance(value, list) else re.split(r"\n+", str(value))
    return [p.strip() for p in raw if p and str(p).strip()]


def build_page(article: dict, idx: int, all_articles: list, date_key: str,
               briefing: str, signals: list, style: str) -> str:
    cls, bg, color = get_cat(article)
    title = article.get("title", "")
    summary = article.get("summary", "")
    category = article.get("category", "")
    timestamp = article.get("timestamp", "")
    canonical = f"{SITE_URL}/{article_path(date_key, idx)}"
    desc = summary[:200]

    img_rel = article.get("image_url") or ""
    img_abs = (f"{SITE_URL}/{img_rel.lstrip('/')}" if img_rel
               else f"{SITE_URL}/images/og-default.jpg")

    # ── 5단계 프레임 (내용 없는 섹션은 통째로 생략하고 번호를 다시 매김) ──
    sections, n = [], 0
    for field, label_en, label_kr, sec_cls in FRAMES:
        body = paras(article.get(field))
        if not body:
            continue
        ps = "\n".join(f"          <p>{esc(p)}</p>" for p in body)
        sections.append(
            f'        <div class="frame-section {sec_cls}">\n'
            f'          <div class="frame-header">\n'
            f'            <span class="frame-step-num">{STEP_NUMS[n]}</span>\n'
            f'            <span class="frame-step-label">{label_en}</span>\n'
            f'            <span class="frame-step-kr">{label_kr}</span>\n'
            f'          </div>\n'
            f'          <div class="frame-body">\n{ps}\n          </div>\n'
            f'        </div>'
        )
        n += 1
    frames_html = "\n".join(sections)

    is_brief = bool(article.get("is_brief")) or not any(
        paras(article.get(f)) for f in ("meaning", "winner", "loser"))
    brief_badge = '<span class="brief-badge">⚡ 속보</span>' if is_brief else ""
    brief_note = f'<div class="brief-note">{esc(BRIEF_NOTE)}</div>' if is_brief else ""

    hero = (f'<img src="{BASE}{esc(img_rel)}" alt="{esc(title)}" class="art-hero">'
            if img_rel else "")

    # ── 관련 기사: 같은 카테고리 우선 (정적 <a>라 크롤러가 따라간다) ──
    others = ([(i, a) for i, a in enumerate(all_articles)
               if i != idx and a.get("category") == category]
              + [(i, a) for i, a in enumerate(all_articles)
                 if i != idx and a.get("category") != category])[:5]
    if others:
        rel_html = "\n".join(
            f'        <a class="rel-item" href="{esc(os.path.basename(article_path(date_key, i)))}">\n'
            f'          <span class="cat-tag {get_cat(a)[0]}">{esc(a.get("category", ""))}</span>\n'
            f'          <div class="rel-title">{esc(a.get("title", ""))}</div>\n'
            f'        </a>'
            for i, a in others)
    else:
        rel_html = '        <div style="color:#aaa;font-size:13px;">관련 기사가 없습니다.</div>'

    if signals:
        signal_html = "\n".join(
            f'        <div class="signal-item">\n'
            f'          <span class="signal-icon">{esc(s.get("icon", ""))}</span>\n'
            f'          <div style="flex:1;min-width:0;">\n'
            f'            <div class="signal-label-txt">{esc(s.get("label", ""))}</div>\n'
            f'            <div class="signal-status">{esc(s.get("status", ""))}</div>\n'
            f'          </div>\n'
            f'        </div>'
            for s in signals)
    else:
        signal_html = ""

    ticker = "  ·  ".join(a.get("title", "") for a in all_articles)
    disp_date = date_key.replace("-", ".")

    ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title,
        "description": desc,
        "image": [img_abs],
        "datePublished": f"{date_key}T09:00:00+09:00",
        "dateModified": f"{date_key}T09:00:00+09:00",
        "url": canonical,
        "mainEntityOfPage": canonical,
        "inLanguage": "ko-KR",
        "author": {"@type": "Organization", "name": "THE SIGNAL KOREA 인텔리전스팀"},
        "publisher": {
            "@type": "NewsMediaOrganization",
            "name": "THE SIGNAL KOREA",
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/images/og-default.jpg"},
        },
    }
    if category:
        ld["articleSection"] = category

    # 공유 링크 (정적 — 링크만 붙여넣어도 각 SNS가 이 페이지 OG를 미리보기로 렌더)
    _u, _t = quote(canonical, safe=""), quote(title)
    _tu = quote(f"{title} {canonical}")
    share_x  = f"https://twitter.com/intent/tweet?text={_t}&url={_u}"
    share_th = f"https://www.threads.net/intent/post?text={_tu}"
    share_tg = f"https://t.me/share/url?url={_u}&text={_t}"
    _sb = ("display:inline-flex;align-items:center;gap:6px;padding:8px 14px;"
           "border:1px solid var(--border);border-radius:6px;font-size:13px;"
           "color:var(--text-muted);background:#fff;cursor:pointer;text-decoration:none;")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)} — THE SIGNAL KOREA</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="THE SIGNAL KOREA">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(img_abs)}">
<meta property="og:locale" content="ko_KR">
<meta property="article:section" content="{esc(category)}">
<meta property="article:published_time" content="{date_key}T09:00:00+09:00">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{esc(img_abs)}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
{style}
</head>
<body>

<div class="signal-bar">
  <div class="inner">
    <span class="signal-label">SIGNAL</span>
    <span class="signal-text">{esc(ticker)}</span>
  </div>
</div>

<header>
  <div class="header-top">
    <a class="logo-block" href="{BASE}index.html">
      <div class="logo-en">THE <span>SIGNAL</span> KOREA</div>
      <div class="logo-kr">한국 산업 인텔리전스 · FACT · MEANING · WINNER · LOSER · ACTION</div>
    </a>
    <div class="header-right">
      <div class="header-date">{disp_date}</div>
      <div style="font-size:11px;color:rgba(255,255,255,0.35);letter-spacing:1px;margin-top:2px;">기술패권 · 공급망전쟁 · 산업전략</div>
    </div>
  </div>
  <nav>
    <div class="nav-inner">
      <div class="nav-cats">
        <a href="{BASE}index.html">전체</a>
        <a href="{BASE}category.html?cat=공급망전쟁">공급망전쟁</a>
        <a href="{BASE}category.html?cat=기술패권">기술패권</a>
        <a href="{BASE}category.html?cat=산업전략">산업전략</a>
        <a href="{BASE}category.html?cat=글로벌분석">글로벌분석</a>
      </div>
      <div class="nav-util">
        <a href="{BASE}search.html">검색</a>
        <a href="{BASE}about.html">소개</a>
        <a href="https://t.me/thesignalkorea" target="_blank" rel="noopener" style="color:var(--accent);font-weight:700;">📡 텔레그램 구독</a>
      </div>
    </div>
  </nav>
</header>

<div class="breadcrumb">
  <div class="bc-inner">
    <a href="{BASE}index.html">홈</a>
    <span class="bc-sep">›</span>
    <a href="{BASE}category.html?cat={esc(category)}">{esc(category)}</a>
    <span class="bc-sep">›</span>
    <span class="bc-current">{esc(title)}</span>
  </div>
</div>

<div class="page-wrap">

  <div class="article-area">
    <article>

      <div class="art-header">
        <div class="art-top-meta">
          <span class="cat-tag {cls}">{esc(category)}</span>
          <span class="art-timestamp">{esc(timestamp)}</span>
          {brief_badge}
        </div>
        <h1 class="art-title">{esc(title)}</h1>
        <div class="art-byline">
          <span class="author">인텔리전스팀</span>
          <span>|</span>
          <span>{disp_date} {esc(timestamp)}</span>
        </div>
      </div>

      <div>{hero}</div>

      <div class="art-summary-box">{esc(summary)}</div>
      {brief_note}

      <div class="five-frame">
{frames_html}
      </div>

      <div style="margin:16px 0 4px;">
        <a href="https://link.coupang.com/a/eVzgl7H5pY" target="_blank" rel="nofollow sponsored noopener" referrerpolicy="unsafe-url" style="display:block;">
          <img src="https://ads-partners.coupang.com/banners/1000915?trackingCode=AF9787280&amp;subId=&amp;traceId=V0-301-969b06e95b87326d-I1000915&amp;w=728&amp;h=90" alt="" style="display:block;width:100%;max-width:728px;height:auto;margin:0 auto;">
        </a>
        <p style="font-size:10.5px;color:#bbb;text-align:right;margin-top:4px;">이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받습니다.</p>
      </div>

      <div class="art-footer">
        <div style="font-size:11px;font-weight:700;color:var(--text-light);letter-spacing:1px;margin-bottom:10px;">KEYWORDS</div>
        <div class="art-tags">
          <span class="art-tag" style="background:{bg};color:{color};">#{esc(category)}</span>
        </div>
        <div class="art-actions" style="margin-top:20px;">
          <a class="back-btn" href="{BASE}index.html">← 목록으로</a>
        </div>

        <div style="margin-top:24px;padding-top:20px;border-top:1px solid var(--border);">
          <div style="font-size:11px;font-weight:700;color:var(--text-light);letter-spacing:1px;margin-bottom:12px;">이 기사 공유</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <a style="{_sb}" href="{share_x}" target="_blank" rel="noopener">𝕏 트위터</a>
            <a style="{_sb}" href="{share_th}" target="_blank" rel="noopener">스레드</a>
            <a style="{_sb}" href="{share_tg}" target="_blank" rel="noopener">텔레그램</a>
            <button style="{_sb}" onclick="if(navigator.share){{navigator.share({{title:document.title,url:'{canonical}'}})}}else{{navigator.clipboard.writeText('{canonical}');this.textContent='링크 복사됨!'}}">🔗 링크 복사</button>
          </div>
          <a href="https://t.me/thesignalkorea" target="_blank" rel="noopener" style="display:inline-block;margin-top:18px;background:var(--accent);color:var(--primary);font-weight:800;padding:11px 20px;border-radius:6px;font-size:13.5px;text-decoration:none;">📡 텔레그램 채널 구독 — 매일 아침 시그널 받기</a>
        </div>
      </div>

    </article>
  </div>

  <aside class="art-sidebar">

    <div class="sb-box">
      <div class="sb-title">다른 기사</div>
{rel_html}
    </div>

    <div class="sb-box editorial-box">
      <div class="sb-title">EDITOR'S BRIEFING</div>
      <div class="editorial-text">{esc(briefing)}</div>
    </div>
{('''
    <div class="sb-box">
      <div class="sb-title">핵심 시그널</div>
''' + signal_html + '''
    </div>''') if signal_html else ''}

  </aside>

</div>

<footer>
  <div class="footer-inner">
    <div>
      <div class="footer-logo">THE <span>SIGNAL</span> KOREA</div>
      <div style="margin-top:6px;line-height:1.9;">
        한국 산업 인텔리전스 · 기술패권 · 공급망전쟁 · 산업전략<br>
        발행인: 대표 | 편집국 | 문의: <a href="#" onclick="openContactModal();return false;" style="color:rgba(255,255,255,.6);text-decoration:underline;">문의하기</a>
      </div>
    </div>
    <div>
      <div class="footer-links">
        <a href="https://t.me/thesignalkorea" target="_blank" rel="noopener" style="color:var(--accent);font-weight:700;">📡 텔레그램 구독</a><a href="{BASE}about.html">소개</a><a href="{BASE}advertising.html">광고문의</a><a href="{BASE}privacy.html">개인정보처리방침</a><a href="{BASE}terms.html">이용약관</a>
      </div>
      <div style="margin-top:8px;text-align:right;">© 2026 The Signal Korea. All rights reserved.</div>
    </div>
  </div>
</footer>

<script src="{BASE}contact-modal.js"></script>
</body>
</html>
"""


def generate_for_date(date_key: str, data: dict, style: str) -> int:
    articles = data.get("articles", [])
    briefing = data.get("editorial_briefing", "") or ""
    signals = data.get("key_signals", []) or []
    os.makedirs(OUT_DIR, exist_ok=True)
    for idx, article in enumerate(articles):
        page = build_page(article, idx, articles, date_key, briefing, signals, style)
        with open(article_path(date_key, idx), "w", encoding="utf-8") as f:
            f.write(page)
    return len(articles)


def load_archive_dates() -> list:
    try:
        with open(f"{ARCHIVE_DIR}/index.json", "r", encoding="utf-8") as f:
            return json.load(f).get("dates", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def generate_all(only_date: str = None) -> int:
    """아카이브 전체(또는 지정 날짜)를 정적 페이지로 생성. 생성된 기사 수를 반환."""
    style = extract_style()
    if not style:
        print("⚠️ article.html에서 <style>을 찾지 못함 — 스타일 없이 생성됨")

    dates = [only_date] if only_date else load_archive_dates()
    total = 0
    for dk in dates:
        try:
            with open(f"{ARCHIVE_DIR}/{dk}.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"   건너뜀 {dk}: {type(e).__name__}")
            continue
        n = generate_for_date(dk, data, style)
        total += n
        print(f"   📄 {dk} — {n}건")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="특정 날짜만 생성 (YYYY-MM-DD)")
    args = ap.parse_args()

    print("🏗️  정적 기사 페이지 생성 시작...")
    total = generate_all(args.date)
    print(f"✅ 완료 — {OUT_DIR}/ 에 기사 {total}건")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
