"""
더 시그널 코리아 (The Signal Korea) — 기사 검수 스크립트
실행: python 기사검수.py [--date YYYY-MM-DD]

기능:
  1. articles.json 또는 지정 날짜 아카이브 기사 품질 검수
  2. 구조 검수 — 5단계 필드 완성도(fact/meaning/winner/loser/action 각 최소 2단락),
     속보(is_brief=True)는 fact/action만, 카테고리 비중(공급망전쟁 목표 50%)
  3. 이미지 파일 검수 — 누락·용량·중복(MD5 해시)
  4. Claude 사실성 검수 — trust_score(1~5) + 의심 주장 + 상태(pass/warning/fail)
  5. Claude 이미지 내용 연관성 검수 — image_keyword가 기사 내용과 맞는지 →
     부적절 시 키워드 수정 + 이미지 재다운로드(기사자동생성.py 다운로더 재사용)
  6. 검수 결과 articles.json에 review 필드로 저장
  7. 소재타임스식 텔레그램 보고 (환경변수 있을 때만)
  8. scripts/review.log 기록
"""

import json
import os
import sys
import hashlib
import argparse
import importlib
import requests
from datetime import datetime, timezone, timedelta
from collections import Counter

# ── 환경변수 ──
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

MODEL    = "claude-sonnet-4-6"   # CLAUDE.md 기준 모델
LOG_DIR  = "scripts"
LOG_FILE = os.path.join(LOG_DIR, "review.log")
KST      = timezone(timedelta(hours=9))
STATUS_EMOJI = {"pass": "✅", "warning": "⚠️", "fail": "❌"}

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
            # 실패 사유(description)까지 남겨야 chat not found / 파싱 오류 등을 바로 진단 가능
            try:
                desc = resp.json().get("description", resp.text[:200])
            except Exception:
                desc = resp.text[:200]
            log(f"Telegram 알림 실패: {resp.status_code} — {desc}", "WARN")
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


# ── Claude 사실성 + 이미지 연관성 검수 ───────────────────────────────
def _stage_preview(article):
    """5단계 필드를 검수용 짧은 미리보기 텍스트로 합친다 (토큰 절약)."""
    parts = []
    for field in ["fact", "meaning", "winner", "loser", "action"]:
        paras = article.get(field, [])
        if isinstance(paras, list) and paras:
            joined = " ".join(paras[:2])
            parts.append(f"[{field}] {joined[:300]}")
    return "\n".join(parts)


def review_articles_with_claude(articles):
    """Claude로 사실성(trust_score) + 이미지 키워드 연관성을 검수.
    ANTHROPIC_API_KEY 없거나 오류 시 빈 리스트 반환(구조 검수는 계속 진행)."""
    if not ANTHROPIC_API_KEY:
        log("ANTHROPIC_API_KEY 없음 — Claude 사실·이미지 검수 건너뜀", "WARN")
        return []
    try:
        import anthropic
    except ImportError:
        log("anthropic 패키지 없음 — Claude 검수 건너뜀", "WARN")
        return []

    summaries = []
    for a in articles:
        summaries.append({
            "id": a.get("id"),
            "category": a.get("category", ""),
            "title": a.get("title", ""),
            "summary": a.get("summary", ""),
            "is_brief": a.get("is_brief", False),
            "content_preview": _stage_preview(a),
            "image_keyword": a.get("image_keyword", ""),
        })

    prompt = f"""당신은 산업·경제 인텔리전스 미디어 '더 시그널 코리아'의 수석 검수 데스크입니다.
오늘 발행된 기사 {len(summaries)}개의 사실성과 이미지 적절성을 검수하세요.

[검수 대상 기사]
{json.dumps(summaries, ensure_ascii=False, indent=2)}

[검수 기준]

1. 사실성 평가 (trust_score 1~5):
   - 언급된 기업·기관명이 실제 존재하고 해당 산업에 종사하는지
   - 수치(시장점유율%, 투자·수출 규모, 성장률, 연도)가 업계 현실과 크게 벗어나지 않는지
   - 법·정책·규제명이 실제 존재하는지 (예: CHIPS Act, 갈륨·게르마늄 수출통제, IRA, 반도체특별법 등)
   - 인용 발언이 출처 없이 창작된 것처럼 지나치게 구체적이지 않은지
   - 사건(수출 규제, 광산 사고, 제재 등)이 공급망·산업 관점에서 개연성이 있는지
   5=거의 모든 내용 검증 가능, 4=대부분 사실로 판단, 3=일부 주의 필요,
   2=의심스러운 주장 다수, 1=명백한 오류 또는 허위 가능성 높음

2. 이미지 키워드 연관성 (image_keyword_ok):
   - image_keyword(영문)가 기사 내용(주제·소재·산업)과 직접 관련 있는지
   - 스톡 이미지 검색에 효과적으로 구체적인지
     (너무 추상적: "industry" → 적절: "gallium semiconductor supply chain")
   - 부적절하면 suggested_image_keyword에 기사 내용에 맞는 영문 2~3단어 제안

review_articles 도구로 전체 검수 결과를 반환하세요."""

    tool = {
        "name": "review_articles",
        "description": "기사 사실성·이미지 검수 결과를 저장합니다",
        "input_schema": {
            "type": "object",
            "properties": {
                "reviews": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "article_id": {"type": "integer"},
                            "trust_score": {"type": "integer", "minimum": 1, "maximum": 5,
                                            "description": "사실성 신뢰도 점수"},
                            "status": {"type": "string", "enum": ["pass", "warning", "fail"],
                                       "description": "pass=문제없음, warning=주의, fail=심각한 오류"},
                            "suspicious_claims": {"type": "array", "items": {"type": "string"},
                                                  "description": "검증 필요한 의심 주장(최대 3개, 각 50자 이내)"},
                            "image_keyword_ok": {"type": "boolean",
                                                 "description": "이미지 키워드가 기사 내용과 연관 있으면 true"},
                            "suggested_image_keyword": {"type": "string",
                                                        "description": "image_keyword_ok=false일 때 대체 영문 키워드"},
                            "notes": {"type": "string", "description": "전반 검수 코멘트(60자 이내)"},
                        },
                        "required": ["article_id", "trust_score", "status",
                                     "suspicious_claims", "image_keyword_ok", "notes"],
                    },
                    "minItems": len(summaries),
                    "maxItems": len(summaries),
                }
            },
            "required": ["reviews"],
        },
    }

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=[tool],
            tool_choice={"type": "tool", "name": "review_articles"},
            messages=[{"role": "user", "content": prompt}],
        )
        block = next(b for b in resp.content if b.type == "tool_use")
        return block.input["reviews"]
    except Exception as e:
        log(f"Claude 검수 오류: {e}", "WARN")
        return []


def apply_image_keyword_fixes(articles, reviews, date_prefix):
    """image_keyword_ok=false인 기사의 키워드를 수정하고 이미지를 재다운로드.
    기사자동생성.py의 _download_single_image를 재사용. 조치 내역 리스트 반환."""
    fixes = []
    to_fix = [r for r in reviews
              if not r.get("image_keyword_ok", True) and r.get("suggested_image_keyword")]
    if not to_fix:
        return fixes

    gen = None
    try:
        gen = importlib.import_module("기사자동생성")
        gen._load_image_history()   # 과거 해시 적재 → 재다운로드 시 중복 방지
    except Exception as e:
        log(f"이미지 재다운로드 모듈 로드 실패(키워드만 수정): {e}", "WARN")

    by_id = {a.get("id"): a for a in articles}
    for r in to_fix:
        a = by_id.get(r["article_id"])
        if not a:
            continue
        old_kw = a.get("image_keyword", "")
        new_kw = r["suggested_image_keyword"]
        a["image_keyword"] = new_kw
        fix = {"id": a.get("id"), "old": old_kw, "new": new_kw, "redownloaded": False}

        if gen is not None:
            idx = a.get("id", 0)
            img_path = f"images/{date_prefix}_article_{idx}.jpg"
            try:
                ok = gen._download_single_image(
                    new_kw, img_path, a.get("category", ""), f"{date_prefix}_{idx}_kw_{new_kw}")
                if ok:
                    a["image_url"] = img_path
                    fix["redownloaded"] = True
            except Exception as e:
                log(f"이미지 재다운로드 오류 [id={idx}]: {e}", "WARN")

        log(f"이미지 키워드 수정 [id={fix['id']}]: '{old_kw}' → '{new_kw}'"
            f"{' (재다운로드 완료)' if fix['redownloaded'] else ''}")
        fixes.append(fix)

    if gen is not None:
        try:
            gen._save_image_history()
        except Exception:
            pass
    return fixes


# ── 메인 검수 로직 ────────────────────────────────────────────────────
def run_review(data_path, label="articles.json", date_prefix=None):
    log(f"=== 기사 검수 시작: {label} ===")
    if date_prefix is None:
        date_prefix = datetime.now(KST).strftime("%Y-%m-%d")

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

    # ⑤ Claude 사실성 + 이미지 연관성 검수
    log("Claude 사실성·이미지 연관성 검수 중...")
    reviews = review_articles_with_claude(articles)
    image_fixes = []
    review_map = {}
    if reviews:
        review_map = {r["article_id"]: r for r in reviews}
        image_fixes = apply_image_keyword_fixes(articles, reviews, date_prefix)

        report_lines.append("\n  [사실성·이미지 검수]")
        for a in articles:
            r = review_map.get(a.get("id"))
            if not r:
                continue
            emoji = STATUS_EMOJI.get(r.get("status"), "✅")
            title = a.get("title", "")[:24]
            report_lines.append(f"    {emoji} #{a.get('id')} {title} (신뢰도 {r.get('trust_score')}/5)")
            if r.get("status") == "fail":
                total_errors += 1
            for claim in r.get("suspicious_claims", [])[:2]:
                report_lines.append(f"        🔎 {claim[:48]}")
                total_warnings += 1
            if not r.get("image_keyword_ok", True):
                report_lines.append(f"        🖼️ 이미지 키워드 → {r.get('suggested_image_keyword','')}")
                total_warnings += 1

        # 검수 결과를 articles.json(또는 아카이브)에 review 필드로 저장
        reviewed_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
        for a in articles:
            r = review_map.get(a.get("id"), {})
            a["review"] = {
                "trust_score": r.get("trust_score", 3),
                "status": r.get("status", "pass"),
                "suspicious_claims": r.get("suspicious_claims", []),
                "image_keyword_ok": r.get("image_keyword_ok", True),
                "notes": r.get("notes", ""),
                "verified_at": reviewed_at,
            }
        data["articles"] = articles
        data["last_reviewed_at"] = reviewed_at
        try:
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log(f"검수 결과 저장 완료 → {data_path} (review 필드 + last_reviewed_at)")
        except Exception as e:
            log(f"검수 결과 저장 오류: {e}", "WARN")

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

    # ── Telegram 보고 (소재타임스식) ──
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        head_emoji = "✅" if passed else "❌"
        lines = [
            f"📋 <b>더 시그널 코리아 검수 보고</b>",
            f"<code>{label}</code>  |  {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}",
            f"{head_emoji} 기사 {len(articles)}건 · 오류 {total_errors} · 경고 {total_warnings}",
            f"카테고리: {dist_str}",
        ]

        # 사실성·이미지 검수 요약 (기사별)
        if review_map:
            lines.append("")
            for a in articles:
                r = review_map.get(a.get("id"))
                if not r:
                    continue
                emoji = STATUS_EMOJI.get(r.get("status"), "✅")
                title = a.get("title", "")[:18]
                lines.append(f"{emoji} [{a.get('id')}] {title}… (신뢰도 {r.get('trust_score')}/5)")
                for claim in r.get("suspicious_claims", [])[:2]:
                    lines.append(f"   🔎 {claim[:46]}")
                if not r.get("image_keyword_ok", True):
                    lines.append(f"   🖼️ 이미지 키워드 → {r.get('suggested_image_keyword','')}")

        # 자동 조치 요약
        if image_fixes:
            redl = sum(1 for f in image_fixes if f.get("redownloaded"))
            lines.append(f"\n🔧 자동 조치: 이미지 키워드 {len(image_fixes)}건 수정"
                         + (f", {redl}건 재다운로드" if redl else ""))

        # 구조/이미지 오류 상세 (Claude 검수 외 항목)
        struct_lines = [l for l in report_lines if "[사실성·이미지 검수]" not in l]
        if not passed and struct_lines:
            lines.append("\n<b>상세</b>:" + "\n".join(struct_lines[:8]))
        elif passed and not review_map:
            lines.append("\n✨ 구조 검수 통과")

        send_telegram("\n".join(lines))

    return passed


# ── 진입점 ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="더 시그널 코리아 기사 검수")
    parser.add_argument("--date", help="검수할 날짜 (YYYY-MM-DD). 미입력 시 articles.json 검수")
    args = parser.parse_args()

    if args.date:
        path  = f"archive/{args.date}.json"
        label = f"archive/{args.date}.json"
        date_prefix = args.date
    else:
        path  = "articles.json"
        label = "articles.json"
        date_prefix = None   # run_review에서 오늘(KST)로 설정

    ok = run_review(path, label, date_prefix)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
