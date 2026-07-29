#!/usr/bin/env python3
"""스레드/X용 카드뉴스 이미지 생성 (1080x1080, 브랜드 스타일).
발행 시 기사별로 cards/{date}-{id}.png 를 만든다.
- 자동 포스팅(X/Threads API)은 별도 토큰 필요 — 이미지 생성까지가 이 모듈의 역할.
- 단독 실행: python 카드뉴스생성.py [YYYY-MM-DD]  (없으면 오늘 articles.json)
브랜드: 네이비 #0a0f1e, 골드 #e8a000."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont

KST = timezone(timedelta(hours=9))
W = H = 1080
NAVY = (10, 15, 30)
GOLD = (232, 160, 0)
WHITE = (245, 247, 250)
MUTED = (150, 160, 175)
OUT_DIR = "cards"

# 폰트 해석 — 맥 우선, 없으면 리눅스(클라우드) 한글 폰트 폴백.
# 한글 폰트를 못 찾으면 RuntimeError → 파이프라인이 카드 생성을 깔끔히 건너뜀(깨진 카드 방지).
def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


KR = _first_existing([
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",           # macOS
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",  # Ubuntu (fonts-nanum)
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
])
EN_BOLD = _first_existing([
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]) or KR

# 카테고리 → (표시색, 라벨)
CAT_COLOR = {
    "기술패권": (216, 60, 60), "공급망전쟁": (232, 160, 0),
    "산업전략": (40, 170, 90), "글로벌분석": (70, 140, 240),
}


def _font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def wrap(draw, text, font, max_w):
    """폭(px)에 맞춰 줄바꿈 (한글은 공백이 적어 글자 단위 폴백)."""
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            # 단어 자체가 너무 길면 글자 단위로 자름
            if draw.textlength(w, font=font) > max_w:
                s = ""
                for ch in w:
                    if draw.textlength(s + ch, font=font) <= max_w:
                        s += ch
                    else:
                        lines.append(s)
                        s = ch
                cur = s
            else:
                cur = w
    if cur:
        lines.append(cur)
    return lines


def build_card(article: dict, date_label: str) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    M = 90  # 여백

    # 상단 골드 라인 + 브랜드
    d.rectangle([0, 0, W, 12], fill=GOLD)
    f_brand = _font(EN_BOLD, 40)
    d.text((M, 70), "THE ", font=f_brand, fill=WHITE)
    x = M + d.textlength("THE ", font=f_brand)
    d.text((x, 70), "SIGNAL", font=f_brand, fill=GOLD)
    x += d.textlength("SIGNAL", font=f_brand)
    d.text((x, 70), " KOREA", font=f_brand, fill=WHITE)
    d.text((M, 122), "한국 산업 인텔리전스", font=_font(KR, 26), fill=MUTED)

    # 카테고리 태그
    cat = article.get("category", "")
    cc = CAT_COLOR.get(cat, GOLD)
    f_cat = _font(KR, 30)
    tw = d.textlength(cat, font=f_cat)
    d.rounded_rectangle([M, 210, M + tw + 44, 268], radius=12, fill=cc)
    d.text((M + 22, 218), cat, font=f_cat, fill=(10, 15, 30) if cat == "공급망전쟁" else WHITE)
    if article.get("is_brief"):
        d.text((M + tw + 64, 218), "⚡ 속보", font=f_cat, fill=GOLD)

    # 제목 (자동 크기 조정 + 줄바꿈)
    title = article.get("title", "")
    size = 72
    while size >= 44:
        f_title = _font(KR, size)
        lines = wrap(d, title, f_title, W - 2 * M)
        lh = int(size * 1.32)
        if len(lines) * lh <= 430:
            break
        size -= 4
    y = 330
    for ln in lines:
        d.text((M, y), ln, font=f_title, fill=WHITE)
        y += lh

    # 골드 구분선
    y = max(y + 24, 800)
    d.rectangle([M, y, M + 90, y + 6], fill=GOLD)

    # 요약 (핵심 한 줄)
    summary = (article.get("summary", "") or "").strip()
    f_sum = _font(KR, 30)
    sum_lines = wrap(d, summary, f_sum, W - 2 * M)[:3]
    ys = y + 30
    for ln in sum_lines:
        d.text((M, ys), ln, font=f_sum, fill=(205, 212, 222))
        ys += 44

    # 하단 푸터
    d.line([M, H - 96, W - M, H - 96], fill=(40, 48, 66), width=2)
    d.text((M, H - 74), "@thesignalkorea", font=_font(EN_BOLD, 30), fill=GOLD)
    foot_r = "thesignalkorea.co.kr"
    fr = _font(EN_BOLD, 28)
    d.text((W - M - d.textlength(foot_r, font=fr), H - 72), foot_r, font=fr, fill=MUTED)
    return img


def generate_for_date(date_key: str, data: dict) -> int:
    if not KR:
        raise RuntimeError("한글 폰트를 찾지 못함 — 카드 생성 건너뜀 (로컬 맥/한글폰트 환경에서 생성됨)")
    os.makedirs(OUT_DIR, exist_ok=True)
    disp = data.get("date_str") or date_key
    n = 0
    for i, a in enumerate(data.get("articles", [])):
        img = build_card(a, disp)
        img.save(f"{OUT_DIR}/{date_key}-{i}.png", "PNG")
        n += 1
    return n


def main():
    date_key = sys.argv[1] if len(sys.argv) > 1 else datetime.now(KST).strftime("%Y-%m-%d")
    path = "articles.json" if date_key == datetime.now(KST).strftime("%Y-%m-%d") else f"archive/{date_key}.json"
    if not os.path.exists(path):
        path = f"archive/{date_key}.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    n = generate_for_date(date_key, data)
    print(f"🎴 카드뉴스 {n}건 생성 — {OUT_DIR}/{date_key}-*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
