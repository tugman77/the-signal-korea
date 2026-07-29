#!/usr/bin/env python3
"""구글 뉴스 퍼블리셔 센터용 로고 2종 생성 (투명 배경 PNG).
- images/logo-rect.png   : 직사각형 워드마크 (THE SIGNAL KOREA)
- images/logo-square.png : 정사각형 아이콘 (네이비 배지 + 골드 시그널 펄스)
브랜드: 네이비 #0a0f1e, 골드 #e8a000."""
import os
from PIL import Image, ImageDraw, ImageFont

NAVY = (10, 15, 30, 255)
GOLD = (232, 160, 0, 255)
EN_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "images"))


def make_rect():
    W, H = 1600, 340
    margin = 90
    usable = W - 2 * margin
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    parts = [("THE ", NAVY), ("SIGNAL ", GOLD), ("KOREA", NAVY)]
    # 폭에 맞는 최대 폰트 크기 자동 탐색
    size = 150
    while size > 40:
        f = ImageFont.truetype(EN_BOLD, size)
        total = sum(d.textlength(t, font=f) for t, _ in parts)
        if total <= usable:
            break
        size -= 2
    asc, desc = f.getmetrics()
    x = (W - total) / 2
    y = (H - (asc + desc)) / 2 - 14
    for text, color in parts:
        d.text((x, y), text, font=f, fill=color)
        x += d.textlength(text, font=f)
    # 하단 골드 언더라인
    uw = int(total)
    ux = (W - uw) // 2
    d.rectangle([ux, y + asc + 18, ux + uw, y + asc + 28], fill=GOLD)
    img.save(os.path.join(OUT, "logo-rect.png"))
    print("생성: images/logo-rect.png", img.size, "폰트", size)


def make_square():
    S = 512
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 네이비 라운드 배지
    pad = 26
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=104, fill=NAVY)
    # 골드 시그널 펄스 (동심원 3겹 + 중앙 점)
    cx, cy = S // 2, S // 2
    for i, r in enumerate([56, 104, 152]):
        w = 20 - i * 3
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=GOLD, width=w)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=GOLD)
    img.save(os.path.join(OUT, "logo-square.png"))
    print("생성: images/logo-square.png", img.size)


if __name__ == "__main__":
    make_rect()
    make_square()
