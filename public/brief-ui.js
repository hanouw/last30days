(() => {
  if (window.parent !== window) document.body.classList.add('embedded');
  const article = document.querySelector('article');
  if (!article) return;
  const headings = [...article.querySelectorAll('h2')];
  const top = headings.find((node) => node.textContent.trim() === '오늘의 핵심');
  const usedUrls = new Set();
  let visuals = [];
  try { visuals = JSON.parse(document.getElementById('brief-visuals')?.textContent || '[]'); } catch { /* Text-only cards remain usable. */ }
  function explainer(spec) {
    if (!spec || !['flow', 'compare', 'facts'].includes(spec.kind) || !Array.isArray(spec.points)) return null;
    const box = document.createElement('div');
    box.className = `brief-explainer brief-explainer-${spec.kind}`;
    box.setAttribute('aria-label', spec.kind === 'flow' ? '사건 흐름' : spec.kind === 'compare' ? '비교' : '핵심 사실');
    const caption = document.createElement('span');
    caption.className = 'brief-explainer-caption';
    caption.textContent = spec.kind === 'flow' ? '무슨 변화가 있었나' : spec.kind === 'compare' ? '한눈에 비교' : '핵심 정보';
    box.appendChild(caption);
    spec.points.slice(0, 3).forEach((point) => {
      if (!point || typeof point.label !== 'string' || typeof point.detail !== 'string') return;
      const row = document.createElement('div');
      row.className = 'brief-explainer-point';
      const label = document.createElement('strong');
      label.textContent = point.label;
      const detail = document.createElement('span');
      detail.textContent = point.detail;
      row.append(label, detail);
      box.appendChild(row);
    });
    return box.querySelectorAll('.brief-explainer-point').length >= 2 ? box : null;
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
      const summaryText = item.textContent.replace(link.textContent, '').replace(/^\s*[-–—]\s*/, '').trim();
      const title = document.createElement('span');
      title.className = 'brief-card-title';
      title.textContent = visuals[index]?.headline || summaryText || link.textContent.trim();
      const summary = document.createElement('span');
      summary.className = 'brief-card-summary';
      summary.textContent = summaryText;
      const label = document.createElement('span');
      label.className = 'brief-card-label';
      label.textContent = `핵심 ${index + 1}`;
      const explanation = explainer(visuals[index]);
      if (explanation) card.classList.add('has-explainer');
      card.append(label, title);
      if (!explanation && typeof visuals[index]?.image === 'string') {
        try {
          const imageUrl = new URL(visuals[index].image);
          if (imageUrl.protocol === 'https:') {
            const image = document.createElement('img');
            image.className = 'brief-card-image';
            image.src = imageUrl.href;
            image.alt = '';
            image.loading = 'lazy';
            image.referrerPolicy = 'no-referrer';
            image.addEventListener('error', () => image.remove());
            card.appendChild(image);
            card.classList.add('has-image');
          }
        } catch { /* Keep the readable text card. */ }
      }
      if (!explanation && title.textContent !== summaryText) card.appendChild(summary);
      if (explanation) card.appendChild(explanation);
      const source = document.createElement('span');
      source.className = 'brief-card-source';
      source.textContent = `${link.hostname.replace(/^www\./, '')} · 원문 보기 ↗`;
      card.appendChild(source);
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
  article.querySelectorAll('.brief-section-list li').forEach((item) => {
    const link = item.querySelector('a[href]');
    if (!link) return;
    const lead = item.textContent.replace(link.textContent, '').trim().replace(/^[·\-–—\s]+|[·\-–—\s]+$/g, '');
    if (!/[가-힣]/.test(lead) || lead.length < 12) return;
    const summary = document.createElement('span');
    summary.className = 'brief-list-summary';
    summary.textContent = lead;
    item.replaceChildren(summary, link);
    link.classList.add('brief-list-source');
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
