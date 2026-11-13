(() => {
  'use strict';
  const keys = { preferences:'element-war:preferences:v1', reading:'element-war:reading:v1' };
  const get = (key, fallback) => { try { const value=JSON.parse(localStorage.getItem(key)); return value && typeof value==='object' && !Array.isArray(value) ? value : fallback; } catch { return fallback; } };
  const set = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } };
  const clamp = (value, low, high) => Math.max(low, Math.min(high, Number(value) || low));
  const root = document.documentElement;
  const toast = (message) => {
    const el = document.querySelector('.toast');
    if (!el) return;
    el.textContent = message;
    el.classList.add('visible');
    window.setTimeout(() => el.classList.remove('visible'), 2600);
  };
  const saved = get(keys.reading, {});

  if (!root.dataset.reader) {
    const rows = [...document.querySelectorAll('[data-episode]')];
    const current = rows.find((row) => Number(row.dataset.episode) === Number(saved.episode));
    if (current) {
      const link = document.querySelector('[data-continue]');
      if (link) {
        link.textContent = '이어서 읽기 ↗';
        link.href = current.getAttribute('href') + '?resume=1';
        link.setAttribute('aria-label', `${saved.episode}화 이어서 읽기`);
      }
      const status = current.querySelector('.read-status');
      if (status) status.textContent = saved.progress >= 0.95 ? '읽음' : '읽는 중';
    }
    let descending = false;
    const sort = document.querySelector('[data-sort]');
    sort?.addEventListener('click', () => {
      descending = !descending;
      const list = document.querySelector('.episode-list');
      rows.sort((a,b) => (Number(a.dataset.episode)-Number(b.dataset.episode)) * (descending ? -1 : 1));
      for (const row of rows) list.appendChild(row);
      sort.textContent = descending ? '최신 화부터 ↑' : '첫 화부터 ↓';
      if (rows.length === 1) toast('현재 첫 번째 이야기를 읽을 수 있습니다.');
    });
    return;
  }

  const prefs = get(keys.preferences, {});
  const font = document.querySelector('#font-size');
  const output = document.querySelector('#font-output');
  const apply = () => {
    prefs.theme = ['paper','sepia','dark'].includes(prefs.theme) ? prefs.theme : 'paper';
    prefs.fontSize = clamp(prefs.fontSize || 19, 17, 25);
    prefs.width = prefs.width === 'wide' ? 'wide' : 'normal';
    root.dataset.theme = prefs.theme;
    root.style.setProperty('--font-size', prefs.fontSize + 'px');
    root.style.setProperty('--reading-width', prefs.width === 'wide' ? '820px' : '680px');
    font.value = prefs.fontSize;
    output.textContent = prefs.fontSize + 'px';
    document.querySelectorAll('[data-theme-choice]').forEach((b) => b.setAttribute('aria-pressed',String(b.dataset.themeChoice === prefs.theme)));
    document.querySelectorAll('[data-width]').forEach((b) => b.setAttribute('aria-pressed',String(b.dataset.width === prefs.width)));
  };
  apply();
  font.addEventListener('input', () => { prefs.fontSize=font.value; apply(); set(keys.preferences,prefs); });
  document.querySelectorAll('[data-theme-choice]').forEach((b) => b.addEventListener('click', () => { prefs.theme=b.dataset.themeChoice; apply(); set(keys.preferences,prefs); }));
  document.querySelectorAll('[data-width]').forEach((b) => b.addEventListener('click', () => { prefs.width=b.dataset.width; apply(); set(keys.preferences,prefs); }));

  const toggle = document.querySelector('.settings-toggle');
  const panel = document.querySelector('#reader-settings');
  const close = (restoreFocus=false) => { panel.hidden=true; toggle.setAttribute('aria-expanded','false'); if (restoreFocus) toggle.focus(); };
  toggle.addEventListener('click', () => { panel.hidden=!panel.hidden; toggle.setAttribute('aria-expanded',String(!panel.hidden)); if (!panel.hidden) panel.querySelector('button').focus(); });
  document.querySelector('[data-settings-close]').addEventListener('click', () => close(true));
  document.addEventListener('keydown', (event) => { if (event.key==='Escape' && !panel.hidden) close(true); });
  document.addEventListener('click', (event) => { if (!panel.hidden && !panel.contains(event.target) && !toggle.contains(event.target)) close(); });

  const episode = Number(document.querySelector('[data-current-episode]').dataset.currentEpisode);
  const article = document.querySelector('.chapter-body');
  let canSave = false, timer;
  const progress = () => {
    const start=article.getBoundingClientRect().top+window.scrollY-100;
    const distance=Math.max(1,article.offsetHeight-window.innerHeight+160);
    return clamp((window.scrollY-start)/distance,0,1);
  };
  const saveProgress = () => {
    if (!canSave) return;
    const value=progress();
    document.querySelector('.reading-progress span').style.width=(value*100)+'%';
    set(keys.reading,{episode,progress:value,savedAt:Date.now()});
  };
  window.addEventListener('scroll', () => { if (!canSave) return; clearTimeout(timer); timer=setTimeout(saveProgress,120); },{passive:true});
  window.addEventListener('pagehide',saveProgress);
  document.addEventListener('visibilitychange',() => { if (document.hidden) saveProgress(); });
  document.querySelector('.back-top').addEventListener('click',()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}));
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    if (new URLSearchParams(location.search).has('resume') && saved.episode === episode && Number.isFinite(saved.progress)) {
      const start=article.getBoundingClientRect().top+window.scrollY-100;
      const distance=Math.max(1,article.offsetHeight-window.innerHeight+160);
      window.scrollTo({top:Math.max(0,start+clamp(saved.progress,0,1)*distance),behavior:'instant'});
      toast('지난번 읽던 곳에서 이어갑니다.');
    }
    canSave=true;
    saveProgress();
  }));
})();
