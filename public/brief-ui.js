(() => {
  if (window.parent !== window) document.body.classList.add('embedded');
  const article = document.querySelector('article');
  if (!article) return;
  const headings = [...article.querySelectorAll('h2')];
  const top = headings.find((node) => node.textContent.trim() === '오늘의 핵심');
  const usedUrls = new Set();
  let visuals = [];
  try { visuals = JSON.parse(document.getElementById('brief-visuals')?.textContent || '[]'); } catch { /* Text-only cards remain usable. */ }
  function draw(canvas, spec) {
    const ctx = canvas.getContext('2d');
    if (!ctx || !spec || !Array.isArray(spec.palette) || !Array.isArray(spec.shapes)) return;
    const w = canvas.width = 620, h = canvas.height = 530;
    const gradient = ctx.createLinearGradient(0, 0, w, h);
    gradient.addColorStop(0, spec.palette[0]);
    gradient.addColorStop(1, spec.palette[1]);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);
    spec.shapes.forEach((shape) => {
      const x = shape.x / 100 * w, y = shape.y / 100 * h;
      const size = shape.size / 100 * Math.min(w, h);
      ctx.strokeStyle = ctx.fillStyle = shape.color;
      ctx.lineWidth = 5;
      ctx.globalAlpha = .82;
      if (shape.type === 'circle') { ctx.beginPath(); ctx.arc(x, y, size / 2, 0, Math.PI * 2); ctx.fill(); }
      if (shape.type === 'rect') { ctx.fillRect(x, y, size, size * .72); }
      if (shape.type === 'line') { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(shape.x2 / 100 * w, shape.y2 / 100 * h); ctx.stroke(); }
      if (shape.type === 'arc') { ctx.beginPath(); ctx.arc(x, y, size / 2, (shape.start || 0) * Math.PI / 180, (shape.end || 180) * Math.PI / 180); ctx.stroke(); }
    });
    ctx.globalAlpha = 1;
  }
  if (top?.nextElementSibling?.tagName === 'UL') {
    const list = top.nextElementSibling;
    const cards = document.createElement('div');
    cards.className = 'brief-cards';
    cards.setAttribute('aria-label', '오늘의 핵심 기사');
    [...list.children].slice(0, 4).forEach((item, index) => {
      const link = item.querySelector('a[href]');
      if (!link) return;
      usedUrls.add(link.href);
      const card = document.createElement('a');
      card.className = 'brief-card';
      card.href = link.href;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';
      if (visuals[index]) {
        const canvas = document.createElement('canvas');
        canvas.className = 'brief-card-art';
        canvas.setAttribute('aria-hidden', 'true');
        card.appendChild(canvas);
        draw(canvas, visuals[index]);
      }
      const title = document.createElement('span');
      title.className = 'brief-card-title';
      title.textContent = link.textContent.trim();
      const summary = document.createElement('span');
      summary.className = 'brief-card-summary';
      summary.textContent = item.textContent.replace(link.textContent, '').replace(/^\s*[-–—]\s*/, '').trim();
      const label = document.createElement('span');
      label.className = 'brief-card-label';
      label.textContent = `핵심 ${index + 1}`;
      card.append(label, title, summary);
      cards.appendChild(card);
    });
    if (cards.children.length) {
      list.replaceWith(cards);
      const controls = document.createElement('div');
      controls.className = 'brief-controls';
      controls.innerHTML = '<button type="button" aria-label="이전 기사">←</button><span class="brief-position"></span><button type="button" aria-label="다음 기사">→</button>';
      cards.after(controls);
      const position = controls.querySelector('.brief-position');
      const update = () => {
        const index = Math.min(cards.children.length - 1, Math.round(cards.scrollLeft / (cards.firstElementChild.offsetWidth + 14)));
        position.textContent = `${index + 1} / ${cards.children.length}`;
      };
      controls.querySelectorAll('button').forEach((button, direction) => button.addEventListener('click', () => {
        cards.scrollBy({ left: (direction ? 1 : -1) * (cards.firstElementChild.offsetWidth + 14), behavior: 'smooth' });
      }));
      cards.addEventListener('scroll', update, { passive: true });
      update();
    }
  }
  const quick = headings.find((node) => node.textContent.trim() === '빠르게 열어볼 링크');
  if (quick) {
    let node = quick.nextElementSibling;
    while (node && !/^H[23]$/.test(node.tagName)) {
      const next = node.nextElementSibling;
      node.remove();
      node = next;
    }
    quick.remove();
  }
  article.querySelectorAll('ul').forEach((list) => {
    list.classList.add('brief-section-list');
    [...list.children].forEach((item) => {
      const url = item.querySelector('a[href]')?.href;
      if (url && usedUrls.has(url)) item.remove();
      else if (url) usedUrls.add(url);
    });
    if (!list.children.length) {
      if (list.previousElementSibling?.tagName === 'H3') list.previousElementSibling.remove();
      list.remove();
    }
  });
  const opportunities = headings.find((node) => node.textContent.trim() === '개발자 해커톤·공모전');
  const opportunityList = opportunities?.nextElementSibling;
  if (opportunityList?.tagName === 'UL') {
    [...opportunityList.children].forEach((item) => {
      const link = item.querySelector('a[href]');
      const title = link?.textContent.trim() || '';
      if (!link || title.length > 90 || /(?:문의드립니다|<path|&lt;|-->)/i.test(title)) {
        item.remove();
        return;
      }
      const meta = item.textContent.slice(title.length).match(/(?:Wevity|Linkareer|Contest Korea|Thinkgood)(?:,\s*D\s*-\s*\d+)?/i)?.[0];
      item.replaceChildren(link, document.createTextNode(meta ? ` · ${meta}` : ''));
    });
    if (!opportunityList.children.length) opportunities.remove(), opportunityList.remove();
  }
  if (window.parent !== window) {
    const report = () => window.parent.postMessage({ type: 'brief-height', height: document.documentElement.scrollHeight }, window.location.origin);
    new ResizeObserver(report).observe(document.body);
    window.addEventListener('load', report);
    report();
  }
})();
