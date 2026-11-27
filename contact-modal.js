// 더 시그널 코리아 문의 모달 — 이메일로 전송 (공개 정적 사이트에는 토큰을 두지 않는다)
// 기존 정적 기사도 뉴스 카테고리와 창작소설 보조 메뉴를 구분한다.
(function () {
  const script = document.currentScript;
  const connectOriginals = function () {
    const inner = document.querySelector('.nav-inner');
    if (inner && script) {
      let utilities = inner.querySelector('.nav-util');
      if (!utilities) {
        utilities = document.createElement('div');
        utilities.className = 'nav-util';
        inner.appendChild(utilities);
      }
      // Old archived pages can still contain the former category link.
      const existing = [...inner.querySelectorAll('a')].filter(function (a) {
        return /\/novel(?:\/|$)/.test(new URL(a.href).pathname);
      });
      const link = existing.shift() || document.createElement('a');
      existing.forEach(function (a) { a.remove(); });
      link.href = new URL('novel/', script.src).href;
      link.textContent = '연재소설';
      link.setAttribute('data-originals-link', '');
      link.setAttribute('aria-label', '시그널 오리지널 연재소설');
      if (link.parentElement !== utilities) utilities.prepend(link);
    }
    const promo = document.getElementById('novel-promo');
    const mobileSlot = document.getElementById('originals-mobile-slot');
    if (promo && mobileSlot) {
      const desktopAnchor = document.createComment('signal-originals-desktop-position');
      promo.before(desktopAnchor);
      const breakpoint = window.matchMedia('(max-width: 768px)');
      const placePromo = function () {
        if (breakpoint.matches) mobileSlot.appendChild(promo);
        else desktopAnchor.parentNode.insertBefore(promo, desktopAnchor.nextSibling);
      };
      placePromo();
      breakpoint.addEventListener('change', placePromo);
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', connectOriginals, { once: true });
  else connectOriginals();
})();

(function () {
  const CONTACT_EMAIL = 'tugman77@gmail.com'; // 도메인 메일(contact@thesignalkorea.com) 개통 시 교체

  /* ── CSS (네이비·골드 톤) ── */
  const s = document.createElement('style');
  s.textContent = `
    #cm-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;align-items:center;justify-content:center;padding:16px}
    #cm-overlay.open{display:flex}
    #cm-box{background:#fff;width:100%;max-width:460px;border-top:4px solid #e8a000;padding:28px 28px 22px;position:relative;max-height:90vh;overflow-y:auto;box-sizing:border-box}
    #cm-close{position:absolute;top:13px;right:16px;background:none;border:none;font-size:20px;cursor:pointer;color:#aaa;line-height:1}
    #cm-close:hover{color:#333}
    #cm-title{font-size:17px;font-weight:900;color:#0a0f1e;margin-bottom:20px}
    .cm-row{margin-bottom:13px}
    .cm-row label{display:block;font-size:12px;font-weight:700;color:#555;margin-bottom:5px;letter-spacing:.3px}
    .cm-row input,.cm-row select,.cm-row textarea{width:100%;border:1px solid #d8dde4;padding:9px 11px;font-size:14px;font-family:inherit;outline:none;box-sizing:border-box;border-radius:0;background:#fff}
    .cm-row input:focus,.cm-row select:focus,.cm-row textarea:focus{border-color:#0a0f1e}
    .cm-row textarea{resize:vertical;min-height:110px}
    .cm-opt{font-size:11px;color:#aaa;font-weight:400}
    #cm-btn{background:#0a0f1e;color:#e8a000;border:none;width:100%;padding:12px;font-size:14px;font-weight:700;cursor:pointer;margin-top:4px;letter-spacing:.3px}
    #cm-btn:hover{background:#e8a000;color:#0a0f1e}
    #cm-btn:disabled{background:#bbb;cursor:not-allowed}
    #cm-feedback{font-size:13px;text-align:center;min-height:18px;margin-top:10px}
    #cm-feedback.ok{color:#15803d}
    #cm-feedback.err{color:#b91c1c}
  `;
  document.head.appendChild(s);

  /* ── HTML ── */
  const wrap = document.createElement('div');
  wrap.id = 'cm-overlay';
  wrap.innerHTML = `
    <div id="cm-box">
      <button id="cm-close" onclick="closeContactModal()" aria-label="닫기">✕</button>
      <div id="cm-title">문의하기</div>
      <div class="cm-row">
        <label>문의 유형</label>
        <select id="cm-type">
          <option>광고 문의</option>
          <option>제휴 · 콘텐츠 제안</option>
          <option>기사 제보</option>
          <option>오류 신고</option>
          <option>기타</option>
        </select>
      </div>
      <div class="cm-row">
        <label>이름 / 회사 <span class="cm-opt">(선택)</span></label>
        <input id="cm-name" type="text" placeholder="홍길동 / OO주식회사" autocomplete="name">
      </div>
      <div class="cm-row">
        <label>연락처 <span class="cm-opt">(이메일 또는 전화번호, 선택)</span></label>
        <input id="cm-contact" type="text" placeholder="답변 받으실 이메일 또는 전화번호">
      </div>
      <div class="cm-row">
        <label>문의 내용 <span style="color:#b91c1c">*</span></label>
        <textarea id="cm-body" placeholder="문의 내용을 자유롭게 입력해 주세요."></textarea>
      </div>
      <button id="cm-btn" onclick="submitContact()">보내기</button>
      <div id="cm-feedback"></div>
    </div>
  `;
  document.body.appendChild(wrap);

  wrap.addEventListener('click', function (e) {
    if (e.target === wrap) closeContactModal();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeContactModal();
  });

  /* ── 공개 API ── */
  window.openContactModal = function (type) {
    wrap.classList.add('open');
    if (type) {
      const sel = document.getElementById('cm-type');
      for (let i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === type) { sel.selectedIndex = i; break; }
      }
    }
    document.getElementById('cm-feedback').textContent = '';
    document.getElementById('cm-body').focus();
  };

  window.closeContactModal = function () {
    wrap.classList.remove('open');
  };

  window.submitContact = function () {
    const type    = document.getElementById('cm-type').value;
    const name    = document.getElementById('cm-name').value.trim();
    const contact = document.getElementById('cm-contact').value.trim();
    const body    = document.getElementById('cm-body').value.trim();
    const fb      = document.getElementById('cm-feedback');

    fb.className = '';
    if (!body) { fb.className = 'err'; fb.textContent = '문의 내용을 입력해 주세요.'; return; }

    const lines = [
      `유형: ${type}`,
      name    ? `이름/회사: ${name}` : '',
      contact ? `연락처: ${contact}` : '',
      '',
      body,
    ].filter((l, i) => i < 3 || l !== '').join('\n');

    const subject = `[더 시그널 코리아 문의] ${type}`;
    window.location.href =
      `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines)}`;

    fb.className = 'ok';
    fb.textContent = '메일 앱이 열립니다. 전송 버튼을 눌러 주세요.';
    setTimeout(closeContactModal, 2500);
  };
})();


/* ── 추천 블로그 배너: 「소재로 읽는 미래」 (2026-11-27 대표님 승인) ──
   공용 스크립트라 홈·기사·기존 정적 기사 사이드바에 모두 붙는다. 끄려면 ENABLED=false. */
(function () {
  const ENABLED = true;
  if (!ENABLED || document.getElementById('sf-promo')) return;
  const URL_ = 'https://sojae-future.vercel.app/?utm_source=thesignalkorea&utm_medium=sidebar_banner&utm_campaign=cross_promo';
  const css = document.createElement('style');
  css.textContent = `
    #sf-promo{display:block;text-decoration:none;color:inherit;background:#0a0f1e;border:1px solid #2a3350;border-top:3px solid #e8a000;padding:16px 16px 14px;position:relative;overflow:hidden;font-family:inherit;transition:box-shadow .15s}
    #sf-promo:hover{box-shadow:0 4px 14px rgba(0,0,0,.12)}
    #sf-promo .sf-label{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.5px;color:#e8a000;border:1px solid #e8a000;padding:2px 7px;margin-bottom:10px}
    #sf-promo .sf-row{display:flex;gap:12px;align-items:center}
    #sf-promo .sf-tile{flex:0 0 54px;height:54px;background:#e8a000;color:#0a0f1e;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1;border:1px solid #e8a000}
    #sf-promo .sf-tile small{font-size:9px;opacity:.75;align-self:flex-start;margin-left:6px}
    #sf-promo .sf-tile b{font-size:22px;font-weight:900;font-family:Georgia,serif}
    #sf-promo .sf-name{font-size:17px;font-weight:900;color:#ffffff;letter-spacing:-.3px;margin:0 0 4px}
    #sf-promo .sf-desc{font-size:13px;line-height:1.5;color:#c9d1e0;margin:0}
    #sf-promo .sf-series{font-size:12.5px;line-height:1.5;color:#c9d1e0;margin:12px 0 12px;padding-top:10px;border-top:1px dashed #2a3350}
    #sf-promo .sf-series strong{color:#ffffff}
    #sf-promo .sf-btn{display:block;text-align:center;font-size:13.5px;font-weight:700;background:#e8a000;color:#0a0f1e;padding:10px}
    #sf-promo:hover .sf-btn{background:#ffb81f}
  `;
  const build = function () {
    const aside = document.querySelector('aside.sidebar, aside.art-sidebar');
    if (!aside || document.getElementById('sf-promo')) return;
    document.head.appendChild(css);
    const a = document.createElement('a');
    a.id = 'sf-promo';
    a.href = URL_;
    a.target = '_blank';
    a.rel = 'noopener';
    a.setAttribute('aria-label', '추천 블로그 소재로 읽는 미래 바로가기 (새 창)');
    a.innerHTML =
      '<span class="sf-label">추천 블로그</span>' +
      '<div class="sf-row"><div class="sf-tile" aria-hidden="true"><small>31</small><b>Ga</b></div>' +
      '<div><p class="sf-name">소재로 읽는 미래</p>' +
      '<p class="sf-desc">반도체·배터리·AI 뒤의<br>소재 이야기를 쉽게 풉니다.</p></div></div>' +
      '<p class="sf-series">연재 <strong>「미래는 소재를 가진 나라가 지배할까?」</strong></p>' +
      '<span class="sf-btn">블로그 바로가기 →</span>';
    const anchor = aside.querySelector('.editorial-box');
    if (anchor) aside.insertBefore(a, anchor);
    else aside.insertBefore(a, aside.firstElementChild);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build, { once: true });
  else build();
})();
