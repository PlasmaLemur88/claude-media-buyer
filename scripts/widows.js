// Widow check for HTML-rendered stills: returns every text block whose LAST rendered line is a single word.
// Rule: never leave one word alone on a text block's last line (reviewers always notice).
// Usage from Playwright:  const bad = await page.evaluate(WIDOWS_JS_SOURCE, {selector, tolerance, minWords})
// Python builders use scripts/widows.py (find_widows(page)), which loads this file.
// A block is checked when it has at least one direct, non-empty text node (so wrappers are skipped and
// the element that actually holds the words is judged). Words are grouped into lines by their rendered top.
(opts) => {
  const o = Object.assign({ selector: "div,p,h1,h2,h3,h4,h5,h6,li,blockquote,figcaption,td", tolerance: 6, minWords: 3 }, opts || {});
  const bad = [];
  for (const el of document.querySelectorAll(o.selector)) {
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || +cs.opacity === 0) continue;
    const r = document.createRange();
    const words = [];
    const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let t;
    while ((t = walk.nextNode())) {
      const re = /\S+/g; let m;
      while ((m = re.exec(t.textContent))) {
        r.setStart(t, m.index); r.setEnd(t, m.index + m[0].length);
        const b = r.getBoundingClientRect();
        if (b.width) words.push([Math.round(b.top), m[0]]);
      }
    }
    if (words.length < o.minWords) continue;
    const lines = [];
    for (const [y, w] of words) {
      const ln = lines.find(l => Math.abs(l.y - y) < o.tolerance);
      if (ln) ln.words.push(w); else lines.push({ y, words: [w] });
    }
    lines.sort((a, b) => a.y - b.y);
    const last = lines[lines.length - 1];
    if (lines.length > 1 && last.words.length === 1) {
      const b = el.getBoundingClientRect();
      bad.push({ text: el.innerText.replace(/\s+/g, " ").slice(0, 80), widow: last.words[0], lines: lines.length,
                 tag: el.tagName.toLowerCase(), cls: el.className || "", box: [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)] });
    }
  }
  return bad;
}
