"""
더 시그널 코리아 (The Signal Korea) — 기사 검수 스크립트
실행: python 기사검수.py [--date YYYY-MM-DD]

기능:
  - articles.json 또는 지정 날짜 아카이브 기사 품질 검수
  - 이미지 누락·중복 감지 (MD5 해시)
  - 5단계 필드 완성도 검사 (fact/meaning/winner/loser/action 각 최소 2단락)
  - 속보(is_brief=True)는 fact/action만 검사
  - 카테고리 비중 확인 (공급망전쟁 목표 50%)
  - Telegram 알림 (환경변수 있을 때만 선택적)
  - scripts/review.log 기록
"""

import json
import os
import sys
import hashlib
import argparse
import requests
from datetime import datetime, timezone, timedelta
from collections import Counter

# ── 환경변수 ──
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

LOG_DIR  = "scripts"
LOG_FILE = os.path.join(LOG_DIR, "review.log")
KST      = timezone(timedelta(hours=9))

# ── 검수 기준 ──
MIN_PARAGRAPHS = {
    "fact":    2,
    "meaning": 2,
    "winner":  2,
    "loser":   2,
    "action":  2,
}
MIN_PARA_LEN = 50      # 최소 단락 길이 (자)
SUPPLY_RATIO_TARGET = 0.50   # 공급망전쟁 목표 비중
FIELD_CHECK_PATTERN = "실제 조달 현장에서는"   # action 마지막 단락 필수 패턴


# ── 로깅 ──────────────────────────────────────────────────────────────
def log(msg, level="INFO"):
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ── Telegram 알림 (선택적) ────────────────────────────────────────────
def send_telegram(message):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return  # 환경변수 없으면 조용히 스킵
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if resp.status_code == 200:
            log("Telegram 알림 전송 완료")
        else:
            log(f"Telegram 알림 실패: {resp.status_code}", "WARN")
    except Exception as e:
        log(f"Telegram 오류: {e}", "WARN")


# ── 이미지 MD5 해시 계산 ─────────────────────────────────────────────
def md5_of_file(path):
    if not path or not os.path.exists(path):
        return None
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


# ── 단일 기사 검수 ────────────────────────────────────────────────────
def check_article(article, idx):
    """기사 하나를 검수하고 오류 목록 반환."""
    errors = []
    warnings = []
    title    = article.get("title", f"(제목없음 #{idx})")
    is_brief = article.get("is_brief", False)

    # 필수 필드 존재 확인
    for field in ["id", "category", "tag_type", "title", "summary", "fact", "action"]:
        if field not in article or article[field] is None:
            errors.append(f"필수 필드 누락: {field}")

    # 카테고리 유효성
    valid_cats = ["기술패권", "공급망전쟁", "산업전략", "글로벌분석"]
    if article.get("category") not in valid_cats:
        errors.append(f"유효하지 않은 카테고리: {article.get('category')}")

    # tag_type 매핑 검사
    cat_tag_map = {
        "기술패권":   "tag-hegemony",
        "공급망전쟁": "tag-supply",
        "산업전략":   "tag-strategy",
        "글로벌분석": "tag-global",
    }
    expected_tag = cat_tag_map.get(article.get("category", ""))
    if expected_tag and article.get("tag_type") != expected_tag:
        warnings.append(f"tag_type 불일치: {article.get('tag_type')} (기대값: {expected_tag})")

    # summary 길이
    summary = article.get("summary", "")
    if len(summary) < 30:
        errors.append(f"summary 너무 짧음 ({len(summary)}자)")
    elif len(summary) > 200:
        warnings.append(f"summary 너무 길 수 있음 ({len(summary)}자)")

    # 5단계 완성도 검사
    if is_brief:
        # 속보: fact + action만 검사
        check_fields = ["fact", "action"]
        skip_fields  = ["meaning", "winner", "loser"]
    else:
        check_fields = ["fact", "meaning", "winner", "loser", "action"]
        skip_fields  = []

    for field in check_fields:
        paras = article.get(field, [])
        if not isinstance(paras, list):
            errors.append(f"{field}: 배열이 아님 (타입: {type(paras).__name__})")
            continue
        min_p = MIN_PARAGRAPHS.get(field, 2)
        if len(paras) < min_p:
            errors.append(f"{field}: 단락 부족 ({len(paras)}개, 최소 {min_p}개 필요)")
        for j, p in enumerate(paras):
            if len(p.strip()) < MIN_PARA_LEN:
                warnings.append(f"{field}[{j}]: 단락 너무 짧음 ({len(p.strip())}자)")

    # action 마지막 단락 현장 경험 패턴 확인
    action_paras = article.get("action", [])
    if action_paras and isinstance(action_paras, list) and action_paras:
        last_para = action_paras[-1].strip()
        if FIELD_CHECK_PATTERN not in last_para:
            warnings.append(f"action 마지막 단락에 현장 경험 패턴 없음 ('{FIELD_CHECK_PATTERN}' 미포함)")

    # 빈 배열 체크 (속보가 아닌데 빈 배열)
    if not is_brief:
        for field in ["meaning", "winner", "loser"]:
            if not article.get(field):
                errors.append(f"{field}: 주력 분석글인데 비어 있음 (is_brief=False)")

    return errors, warnings, title


# ── 이미지 검수 ──────────────────────────────────────────────────────
def check_images(articles):
    """이미지 누락·중복 감지. {idx: issues} 반환."""
    image_issues = {}
    hash_map = {}   # md5 → idx (중복 감지)

    for i, a in enumerate(articles):
        issues = []
        img_path = a.get("image_url")

        if not img_path:
            issues.append("이미지 URL 없음 (None)")
        elif not os.path.exists(img_path):
            issues.append(f"이미지 파일 없음: {img_path}")
        else:
            # 파일 크기 확인
            size = os.path.getsize(img_path)
            if size < 5000:
                issues.append(f"이미지 파일 크기 너무 작음: {size} bytes")

            # 중복 감지
            md5 = md5_of_file(img_path)
            if md5:
                if md5 in hash_map:
                    issues.append(f"이미지 중복 감지: 기사 #{hash_map[md5]}와 동일한 이미지")
                else:
                    hash_map[md5] = i

        if issues:
            image_issues[i] = issues

    return image_issues


# ── 카테고리 비중 확인 ───────────────────────────────────────────────
def check_category_ratio(articles):
    dist = Counter(a.get("category", "기타") for a in articles)
    total = len(articles)
    issues = []

    supply_count = dist.get("공급망전쟁", 0)
    supply_ratio = supply_count / total if total else 0

    if supply_ratio < SUPPLY_RATIO_TARGET * 0.7:  # 목표의 70% 미만이면 경고
        issues.append(
            f"공급망전쟁 비중 저조: {supply_count}/{total} ({supply_ratio:.0%}, 목표 {SUPPLY_RATIO_TARGET:.0%})"
        )

    return dist, issues


# ── 메인 검수 로직 ────────────────────────────────────────────────────
def run_review(data_path, label="articles.json"):
    log(f"=== 기사 검수 시작: {label} ===")

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        log(f"파일 없음: {data_path}", "ERROR")
        return False
    except json.JSONDecodeError as e:
        log(f"JSON 파싱 오류: {e}", "ERROR")
        return False

    articles = data.get("articles", [])
    if not articles:
        log("기사 없음 (articles 배열이 비어 있음)", "ERROR")
        return False

    log(f"기사 {len(articles)}건 검수 중...")
    total_errors   = 0
    total_warnings = 0
    report_lines   = []

    # ① 기사별 검수
    for i, a in enumerate(articles):
        errors, warnings, title = check_article(a, i)
        if errors or warnings:
            report_lines.append(f"\n  기사 #{i}: {title}")
            for e in errors:
                report_lines.append(f"    ❌ {e}")
                total_errors += 1
            for w in warnings:
                report_lines.append(f"    ⚠️  {w}")
                total_warnings += 1
        else:
            log(f"  기사 #{i} [{a.get('category')}] OK — {title[:30]}...")

    # ② 이미지 검수
    img_issues = check_images(articles)
    if img_issues:
        report_lines.append("\n  [이미지 검수]")
        for idx, issues in img_issues.items():
            title = articles[idx].get("title", f"#{idx}")[:30]
            for iss in issues:
                report_lines.append(f"    ⚠️  기사 #{idx} ({title}): {iss}")
                total_warnings += 1

    # ③ 카테고리 비중 확인
    dist, cat_issues = check_category_ratio(articles)
    dist_str = ", ".join(f"{k}:{v}건" for k, v in dist.most_common())
    log(f"  카테고리 분포: {dist_str}")
    for iss in cat_issues:
        report_lines.append(f"\n  ⚠️  {iss}")
        total_warnings += 1

    # ④ 필수 메타 확인
    if not data.get("editorial_briefing"):
        report_lines.append("\n  ⚠️  editorial_briefing 없음")
        total_warnings += 1
    if not data.get("key_signals"):
        report_lines.append("\n  ⚠️  key_signals 없음")
        total_warnings += 1

    # ── 결과 집계 ──
    passed = total_errors == 0
    status = "✅ PASS" if passed else "❌ FAIL"
    summary = (
        f"\n{'='*50}\n"
        f"검수 결과: {status}\n"
        f"기사 수: {len(articles)}건\n"
        f"오류: {total_errors}건, 경고: {total_warnings}건\n"
        f"카테고리: {dist_str}\n"
    )
    if report_lines:
        summary += "상세:\n" + "\n".join(report_lines) + "\n"
    summary += "=" * 50

    log(summary)

    # ── Telegram 알림 ──
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        emoji = "✅" if passed else "❌"
        tg_msg = (
            f"{emoji} <b>더 시그널 코리아 검수</b>\n"
            f"<code>{label}</code>\n"
            f"기사 {len(articles)}건 | 오류 {total_errors} | 경고 {total_warnings}\n"
            f"카테고리: {dist_str}"
        )
        if not passed and report_lines:
            tg_msg += "\n\n상세:\n" + "\n".join(report_lines[:10])  # 최대 10줄
        send_telegram(tg_msg)

    return passed


# ── 진입점 ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="더 시그널 코리아 기사 검수")
    parser.add_argument("--date", help="검수할 날짜 (YYYY-MM-DD). 미입력 시 articles.json 검수")
    args = parser.parse_args()

    if args.date:
        path  = f"archive/{args.date}.json"
        label = f"archive/{args.date}.json"
    else:
        path  = "articles.json"
        label = "articles.json"

    ok = run_review(path, label)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
