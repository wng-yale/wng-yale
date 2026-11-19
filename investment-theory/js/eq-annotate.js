/* Clickable equation terms.
   In the TeX, wrap a term as \htmlClass{eqt t-KEY}{...}. Inside the same .equation block, add
   <dl class="eq-terms"><dt data-t="KEY">Name</dt><dd>Explanation</dd> ...</dl>.
   Clicking a term shows its name and explanation in a panel under the equation. */
(function () {
  function annotate() {
    document.querySelectorAll('.equation').forEach(function (eq) {
      var dl = eq.querySelector('dl.eq-terms');
      if (!dl || eq.dataset.eqAnnotated) return;
      eq.dataset.eqAnnotated = '1';
      var defs = {};
      dl.querySelectorAll('dt').forEach(function (dt) {
        var dd = dt.nextElementSibling;
        defs[dt.dataset.t] = { name: dt.innerHTML, text: dd ? dd.innerHTML : '' };
      });
      dl.hidden = true;
      var panel = document.createElement('div');
      panel.className = 'eq-panel';
      panel.setAttribute('aria-live', 'polite');
      panel.innerHTML = '<span class="eq-hint">Click any part of the equation for its name and meaning.</span>';
      eq.appendChild(panel);
      var terms = [].slice.call(eq.querySelectorAll('.eqt')).filter(function (el) {
        var k = (el.className.match(/\bt-([\w-]+)/) || [])[1]; el._eqKey = k; return k && defs[k];
      });
      function show(el) {
        terms.forEach(function (t) { t.classList.remove('eqt-on'); });
        el.classList.add('eqt-on');
        var d = defs[el._eqKey];
        panel.innerHTML = '<strong>' + d.name + '.</strong> ' + d.text;
      }
      // KaTeX stacks fractions and radicals with overlapping spans, so the element under the pointer is often the
      // outer term. Choose instead the smallest term whose glyphs contain the click point.
      function box(el) {
        var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        el.querySelectorAll('.mord,.mop,.mbin,.mrel,.mpunct,.minner,.sqrt,.frac-line').forEach(function (g) {
          var r = g.getBoundingClientRect(); if (!r.width || !r.height) return;
          x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom);
        });
        return [x0, y0, x1, y1];
      }
      var root = eq.querySelector('.katex-display') || eq;
      function pick(ev) {
        var best = null, area = 1e18;
        terms.forEach(function (t) {
          var b = box(t);
          if (ev.clientX >= b[0] - 1 && ev.clientX <= b[2] + 1 && ev.clientY >= b[1] - 1 && ev.clientY <= b[3] + 1) {
            var a = (b[2] - b[0]) * (b[3] - b[1]); if (a < area) { area = a; best = t; }
          }
        });
        return best;
      }
      root.addEventListener('click', function (ev) { var t = pick(ev); if (t) show(t); });
      root.addEventListener('mousemove', function (ev) {
        var t = pick(ev);
        terms.forEach(function (x) { x.classList.toggle('eqt-hover', x === t); });
        root.style.cursor = t ? 'pointer' : '';
      });
      root.addEventListener('mouseleave', function () { terms.forEach(function (x) { x.classList.remove('eqt-hover'); }); });
      terms.forEach(function (el) {
        el.setAttribute('role', 'button');
        el.setAttribute('tabindex', '0');
        el.setAttribute('aria-label', defs[el._eqKey].name.replace(/<[^>]*>/g, ''));
        el.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); ev.stopPropagation(); show(el); } });
      });
    });
  }
  window.eqAnnotate = annotate;
  if (document.querySelector('.equation .katex')) annotate();
})();
