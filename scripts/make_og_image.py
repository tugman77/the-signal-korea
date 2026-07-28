#!/usr/bin/env python3
"""브랜드 기본 공유 이미지(og:image, 1200x630) 생성.
SNS(카카오톡·네이버·X 등)에 홈/기사 링크 공유 시 뜨는 대표 썸네일.
전용 이미지가 없을 때 한 번 실행해 images/og-default.jpg 를 만든다."""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
NAVY = (10, 15, 30)        # #0a0f1e
GOLD = (232, 160, 0)       # #e8a000
WHITE = (255, 255, 255)
MUTED = (150, 160, 175)

KR_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
EN_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

img = Image.new("RGB", (W, H), NAVY)
d = ImageDraw.Draw(img)

# 상단 골드 라인
d.rectangle([0, 0, W, 8], fill=GOLD)
# 좌측 골드 액센트 바
d.rectangle([90, 210, 104, 430], fill=GOLD)

f_title = ImageFont.truetype(EN_BOLD, 92)
f_tag = ImageFont.truetype(KR_FONT, 34)
f_kr = ImageFont.truetype(KR_FONT, 30)
f_url = ImageFont.truetype(EN_BOLD, 28)

# THE SIGNAL KOREA (SIGNAL 골드)
x, y = 140, 230
for text, color in [("THE ", WHITE), ("SIGNAL ", GOLD), ("KOREA", WHITE)]:
    d.text((x, y), text, font=f_title, fill=color)
    x += d.textlength(text, font=f_title)

# 한글 로고
d.text((142, 340), "더 시그널 코리아", font=f_kr, fill=MUTED)

# 태그라인
d.text((142, 400), "한국 산업 인텔리전스 · 기술패권 · 공급망전쟁 · 산업전략",
       font=f_tag, fill=(210, 215, 225))

# 하단 URL
d.text((142, 540), "www.thesignalkorea.co.kr", font=f_url, fill=GOLD)

out = os.path.join(os.path.dirname(__file__), "..", "images", "og-default.jpg")
img.save(os.path.abspath(out), "JPEG", quality=88)
print("생성:", os.path.abspath(out))
