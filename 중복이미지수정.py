#!/usr/bin/env python3
"""
더 시그널 코리아 — 기존 중복 이미지 일괄 교체 스크립트 (일회성 유지보수)
실행: python3 중복이미지수정.py

동작:
  1. images/*.jpg 전체 MD5 → 완전 동일한 중복 그룹 탐지
  2. 각 그룹에서 1장만 유지, 나머지는 교체 대상
  3. 교체는 기사 카테고리별 Unsplash 풀에서 선택 → 다운로드 후 MD5가
     '이미 확정된 모든 이미지 해시'와 겹치면 다음 후보로 넘어감(전역 중복 0 보장)
  4. 풀 소진/실패 시 picsum(파일명 시드)로 반드시 고유 이미지 확보
API 키 불필요 (Unsplash 이미지 CDN 직접 URL 사용).
"""
from __future__ import annotations
import json, os, hashlib, urllib.request, time

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR  = os.path.join(SCRIPT_DIR, "images")
ARCHIVE_DIR = os.path.join(SCRIPT_DIR, "archive")

# ── 카테고리별 대형 Unsplash 풀 ──────────────────────────────
BIG_POOL = {
    "공급망전쟁": [
        "photo-1586528116311-ad8dd3c8310d",  # 컨테이너 항구
        "photo-1494412574643-ff11b0a5c1c3",  # 화물선
        "photo-1578575437130-527eed3abbec",  # 컨테이너선 접안
        "photo-1473341304170-971dccb5ac1e",  # 고압 송전탑
        "photo-1504711434969-e33886168f5c",  # 제철소 용융 쇳물
        "photo-1574482620826-40685ca5ebd2",  # 금속 생산라인
        "photo-1495576775051-8af0d10f68d1",  # 제철·철강 생산
        "photo-1545193544-312489b2d26c",     # 물류 트럭
        "photo-1558618666-fcd25c85cd64",     # 글로벌 해운 항로
        "photo-1586769852044-692d6e3703f0",  # 세계 공급망 지도
        "photo-1521790361543-f645cf042ec4",  # 화물 항공기
        "photo-1488229297570-58520851e868",  # 화물선 드론 항공뷰
        "photo-1582139329536-e7284fece509",  # 건설 크레인 군집
    ],
    "기술패권": [
        "photo-1518770660439-4636190af475",  # PCB 회로기판 클로즈업
        "photo-1563770660941-20978e870e26",  # 반도체 칩 클로즈업
        "photo-1601597111158-2fceff292cdc",  # 반도체 웨이퍼
        "photo-1591799265444-d66432b91588",  # AMD Ryzen CPU 칩
        "photo-1562408590-e32931084e23",     # PCB 회로기판 (파랑)
        "photo-1597852074816-d933c7d2b988",  # 전자부품 HDD 내부
        "photo-1581092918056-0c4c3acd3789",  # 전자기기 납땜 작업
        "photo-1451187580459-43490279c0fa",  # 서버 데이터센터 랙
        "photo-1526374965328-7f61d4dc18c5",  # 코드 스크린 (매트릭스)
        "photo-1555680202-c86f0e12f086",     # 컴퓨터 마더보드
        "photo-1558494949-ef010cbdcc31",     # 광섬유 케이블
    ],
    "산업전략": [
        "photo-1565514020179-026b92b84bb6",  # 산업 공장 야간
        "photo-1504328345606-18bbc8c9d7d1",  # 용접사 클로즈업
        "photo-1504917595217-d4dc5ebe6122",  # 금속 용접 불꽃
        "photo-1567789884554-0b844b597180",  # 자동차 공장 로봇
        "photo-1541888946425-d81bb19240f5",  # 건설 현장 엔지니어
        "photo-1581094244429-b9b51e78f1d7",  # 건설 현장 항공뷰
        "photo-1565791380713-1756b9a05343",  # 화학 플랜트 항공뷰
        "photo-1581092160607-ee22621dd758",  # 엔지니어 기계 작업
        "photo-1527515637462-cff94eecc1ac",  # 채석장·광산 암반
        "photo-1531538606174-0f90ff5dce83",  # 광물·금 원석
        "photo-1565793298595-6a879b1d9492",  # 광산 덤프트럭
        "photo-1578375819537-b95e00c82429",  # 금속 제련 용광로
    ],
    "글로벌분석": [
        "photo-1524522173746-f628baad3644",  # 세계 지도 디지털
        "photo-1526304640581-d334cdbbf45e",  # 데이터 시각화
        "photo-1454165804606-c3d57bc86b40",  # 비즈니스 미팅 계약
        "photo-1529156069898-49953e39b3ac",  # 글로벌 팀 회의
        "photo-1535320903710-d993d3d77d29",  # 세계 지도 핀
        "photo-1611974789855-9c2a0a7236a3",  # 트레이딩 화면
        "photo-1444653614773-995cb1ef9efa",  # 신문·경제면
        "photo-1590283603385-17ffb3a7f29f",  # 금융 데이터
    ],
}
UNSPLASH_BASE = "https://images.unsplash.com/{id}?w=800&h=450&fit=crop&auto=format"


def md5_bytes(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def md5_file(path: str) -> str:
    with open(path, 'rb') as f:
        return md5_bytes(f.read())


def fetch(url: str) -> bytes | None:
    """URL에서 이미지 바이트 반환 (실패 시 None)."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        return data if len(data) > 5000 else None
    except Exception as e:
        print(f"      다운로드 오류: {e}")
        return None


def main():
    all_files = sorted(f for f in os.listdir(IMAGES_DIR) if f.endswith('.jpg'))

    # 1. MD5 → 파일 목록
    hash_to_files: dict[str, list[str]] = {}
    for fname in all_files:
        hash_to_files.setdefault(md5_file(os.path.join(IMAGES_DIR, fname)), []).append(fname)

    dup_groups = {h: fs for h, fs in hash_to_files.items() if len(fs) > 1}
    to_replace = [f for fs in dup_groups.values() for f in sorted(fs)[1:]]  # 각 그룹 첫 장 유지
    print(f"중복 그룹 {len(dup_groups)}개 · 교체 대상 {len(to_replace)}장\n")
    if not dup_groups:
        print("중복 없음 — 모두 정상입니다.")
        return

    # 2. 유지되는(교체 안 하는) 이미지들의 해시 = 전역 확정 해시 시드
    replace_set = set(to_replace)
    used_hashes: set[str] = {
        md5_file(os.path.join(IMAGES_DIR, f)) for f in all_files if f not in replace_set
    }

    # 3. 카테고리 로드
    article_cat: dict[str, str] = {}
    for fname in os.listdir(ARCHIVE_DIR):
        if not fname.endswith('.json') or fname == 'index.json':
            continue
        date_str = fname.replace('.json', '')
        try:
            with open(os.path.join(ARCHIVE_DIR, fname), encoding='utf-8') as f:
                data = json.load(f)
            for i, a in enumerate(data.get('articles', [])):
                article_cat[f"{date_str}_article_{i}"] = a.get('category', '글로벌분석')
        except Exception:
            pass

    # 4. 교체 — 후보 다운로드 후 해시가 전역에서 고유할 때만 확정
    ok = 0
    for fname in to_replace:
        key = fname.replace('.jpg', '')
        cat = article_cat.get(key, '글로벌분석')
        dest = os.path.join(IMAGES_DIR, fname)

        # 후보 순서: 해당 카테고리 풀 → 다른 카테고리 풀 → picsum(고유 시드 여러 개)
        candidates = list(BIG_POOL.get(cat, []))
        for c, ids in BIG_POOL.items():
            if c != cat:
                candidates += ids
        candidate_urls = [UNSPLASH_BASE.format(id=i) for i in candidates]
        candidate_urls += [f"https://picsum.photos/seed/{key}-{n}/800/450" for n in range(5)]

        print(f"교체: {fname} [{cat}]")
        done = False
        for url in candidate_urls:
            data = fetch(url)
            if not data:
                continue
            h = md5_bytes(data)
            if h in used_hashes:
                continue  # 이미 쓰인 이미지 → 다음 후보
            with open(dest, 'wb') as f:
                f.write(data)
            used_hashes.add(h)
            src = "picsum" if "picsum" in url else "unsplash"
            print(f"   ✅ {src} 확정 (md5={h[:8]})")
            ok += 1
            done = True
            break
        if not done:
            print(f"   ❌ 실패 — 원본 유지: {fname}")

    # 5. 검증
    final_hashes = [md5_file(os.path.join(IMAGES_DIR, f))
                    for f in all_files]
    remaining = len(final_hashes) - len(set(final_hashes))
    print(f"\n=== 완료: 교체 {ok}/{len(to_replace)}장 · 남은 중복 {remaining}개 ===")
    print("✅ 모든 이미지 고유" if remaining == 0 else "⚠️ 잔여 중복 있음 — 재실행 필요")


if __name__ == "__main__":
    main()
