/*!
 * sd-tape.js — "Fixed supply, shifting demand" price-tape animation
 * For: An Introduction to Investment Theory (W. N. Goetzmann)
 * No dependencies. Vanilla ES2017. ~10 KB.
 *
 * Usage:
 *   <div data-sd-tape></div>
 *   <script src="sd-tape.js" defer></script>
 * or programmatically:
 *   const ctl = SDTape.mount(element, { seed: 7, autoplay: true });
 *   ctl.pause(); ctl.play(); ctl.destroy();
 *
 * Model (one tick = one frame):
 *   Inverse demand for shares:   P = a_t - b_t * (Q - z_t)
 *   Fixed supply (float):        Q = Qbar
 *   Market price:                P_t = a_t - b_t * (Qbar - z_t)
 *   a_t  beliefs about payoff (intercept)  - mean-reverting or random walk
 *   b_t  slope = price impact of a share   - tracks the risk-aversion setting
 *   z_t  order-flow shock (horizontal shift of demand), AR(1)
 * Under CARA-normal investors: a = E[X]/R, b = gamma*sigma^2/R, z = noise demand.
 */
(function (global) {
  "use strict";

  var CSS = [
    ".sdt{--sdt-bg:#fcfcfb;--sdt-ink:#1a1a19;--sdt-muted:#898781;--sdt-grid:#e1e0d9;--sdt-axis:#c3c2b7;",
    "--sdt-price:#eb6834;--sdt-slope:#6250d6;--sdt-demand:#2a78d6;--sdt-supply:#898781;--sdt-border:rgba(0,0,0,.15);",
    "font:inherit;color:var(--sdt-ink);max-width:760px;margin:1.5em 0}",
    ".sdt-legend{display:flex;flex-wrap:wrap;gap:14px;font-size:.8em;color:var(--sdt-muted);margin-bottom:6px}",
    ".sdt-legend span{display:inline-flex;align-items:center;gap:5px}",
    ".sdt-sw{width:10px;height:10px;border-radius:2px;display:inline-block}",
    ".sdt-canvas{position:relative;width:100%}",
    ".sdt-canvas canvas{display:block}",
    ".sdt-row{display:flex;align-items:center;gap:10px;margin-top:10px;font-size:.85em}",
    ".sdt-row label{flex:0 0 auto;width:8.5em;color:var(--sdt-muted)}",
    ".sdt-row input{flex:1 1 auto;min-width:0}",
    ".sdt-row output{flex:0 0 2.6em;text-align:right;font-variant-numeric:tabular-nums}",
    ".sdt-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}",
    ".sdt-btns button{font:inherit;font-size:.85em;padding:.4em .9em;border:1px solid var(--sdt-border);",
    "border-radius:6px;background:transparent;color:var(--sdt-ink);cursor:pointer}",
    ".sdt-btns button:hover{background:rgba(127,127,127,.08)}",
    ".sdt-read{font-size:.8em;color:var(--sdt-muted);margin-top:8px;font-variant-numeric:tabular-nums}",
    ".sdt-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}"
  ].join("");

  function injectCSS() {
    if (document.getElementById("sdt-style")) return;
    var s = document.createElement("style");
    s.id = "sdt-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // small seeded RNG so the opening path is reproducible
  function rng(seed) {
    var t = seed >>> 0 || 1;
    return function () {
      t += 0x6d2b79f5;
      var r = Math.imul(t ^ (t >>> 15), 1 | t);
      r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  function mount(root, opts) {
    opts = opts || {};
    injectCSS();
    root.classList.add("sdt");
    root.innerHTML =
      '<div class="sdt-legend" aria-hidden="true">' +
      '<span><i class="sdt-sw" style="background:var(--sdt-price)"></i>Price</span>' +
      '<span><i class="sdt-sw" style="background:var(--sdt-slope)"></i>Demand slope (risk aversion)</span>' +
      '<span><i class="sdt-sw" style="background:var(--sdt-demand)"></i>Demand</span>' +
      '<span><i class="sdt-sw" style="background:var(--sdt-supply);height:3px"></i>Supply (fixed float)</span></div>' +
      '<div class="sdt-canvas"><canvas role="img" aria-label="Animated diagram: a shifting demand curve crosses a fixed vertical supply of shares; the crossing price is traced onto a scrolling price chart, with a second chart of the demand slope."></canvas></div>' +
      '<div class="sdt-row"><label for="sdt-flow">Order-flow shocks</label><input type="range" min="0" max="10" step="1" value="5" data-k="flow"><output>5</output></div>' +
      '<div class="sdt-row"><label for="sdt-ra">Risk aversion</label><input type="range" min="0.4" max="1" step="0.05" value="0.6" data-k="ra"><output>0.60</output></div>' +
      '<div class="sdt-btns">' +
      '<button type="button" data-a="play">Pause</button>' +
      '<button type="button" data-a="issue">Issue shares</button>' +
      '<button type="button" data-a="rw">Beliefs: mean-reverting</button></div>' +
      '<div class="sdt-read" aria-live="off"></div>';

    var uid = "sdt" + Math.random().toString(36).slice(2, 7);
    var inputs = root.querySelectorAll(".sdt-row input");
    var labels = root.querySelectorAll(".sdt-row label");
    for (var i = 0; i < inputs.length; i++) { inputs[i].id = uid + i; labels[i].htmlFor = uid + i; }

    var cv = root.querySelector("canvas"), box = root.querySelector(".sdt-canvas");
    var ctx = cv.getContext("2d"), readEl = root.querySelector(".sdt-read");
    var W = 0, H = 0, dpr = 1, col = {}, font = "sans-serif";

    function readTheme() {
      var cs = getComputedStyle(root);
      ["bg", "ink", "muted", "grid", "axis", "price", "slope", "demand", "supply"].forEach(function (k) {
        col[k] = cs.getPropertyValue("--sdt-" + k).trim();
      });
      font = cs.fontFamily || "sans-serif";
    }
    function size() {
      dpr = global.devicePixelRatio || 1;
      W = box.clientWidth;
      H = Math.round(Math.max(260, Math.min(420, W * 0.6)));
      box.style.height = H + "px";
      cv.width = W * dpr; cv.height = H * dpr;
      cv.style.width = W + "px"; cv.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      readTheme();
    }

    // ---- model state ----
    var R = rng(opts.seed || 7);
    function g() { var u = R() || 1e-9, v = R(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
    var A0 = 90, Q0 = 50, Qt = 50, bBar = 0.6, b = 0.6, a = A0, z = 0, flow = 5, rw = false;
    var hp = [], hb = [], MAXH = 2000;
    var pMin = 0, pMax = 100, bMin = 0.3, bMax = 1.05;

    function step() {
      b += 0.04 * (bBar - b) + 0.004 * g();
      b = Math.max(0.32, Math.min(1.03, b));
      z += -0.015 * z + 0.8 * (flow / 5) * g();
      if (rw) {
        a += 0.3 * g();
        var p = a - b * (Q0 - z);                      // soft walls keep the tape on screen
        if (p < pMin + 12) a += 0.2; if (p > pMax - 12) a -= 0.2;
      } else {
        a += 0.01 * (A0 - a) + 0.25 * g();
      }
      Q0 += (Qt - Q0) * 0.04;
      hp.push(a - b * (Q0 - z)); hb.push(b);
      if (hp.length > MAXH) { hp.shift(); hb.shift(); }
    }

    function draw() {
      if (!W) return;
      ctx.clearRect(0, 0, W, H);
      ctx.font = "11px " + font;
      var sdW = Math.max(120, Math.round(W * 0.36)), tapeL = 26, tapeR = W - sdW - 12, sdL = tapeR + 12, sdR = W - 6;
      var pT = 16, pB = Math.round(H * 0.66), bT = pB + 34, bB = H - 6;
      var yP = function (p) { return pT + (pMax - p) / (pMax - pMin) * (pB - pT); };
      var yB = function (v) { return bT + (bMax - v) / (bMax - bMin) * (bB - bT); };
      var qx = function (q) { return sdL + q / 100 * (sdR - sdL); };
      function hl(y, x0, x1, c) { y = Math.round(y) + 0.5; ctx.strokeStyle = c; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke(); }

      ctx.fillStyle = col.muted; ctx.textAlign = "right"; ctx.textBaseline = "middle";
      for (var p = 20; p <= 80; p += 20) { hl(yP(p), tapeL, sdR, col.grid); ctx.fillText(p, tapeL - 4, yP(p)); }
      for (var v = 0.4; v <= 1.01; v += 0.2) { hl(yB(v), tapeL, tapeR, col.grid); ctx.fillText(v.toFixed(1), tapeL - 4, yB(v)); }
      hl(pB, tapeL, tapeR, col.axis); hl(pB, sdL, sdR, col.axis);
      ctx.strokeStyle = col.axis; ctx.beginPath(); ctx.moveTo(sdL + 0.5, pT); ctx.lineTo(sdL + 0.5, pB); ctx.stroke();
      ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
      ctx.fillText("Price", tapeL, pT - 4);
      ctx.fillText("Demand slope", tapeL, bT - 8);
      ctx.textAlign = "right";
      ctx.fillText("time →", tapeR, pB + 14);
      ctx.fillText("shares →", sdR, pB + 14);

      // supply and demand (clipped to panel)
      var sx = qx(Q0);
      ctx.save(); ctx.beginPath(); ctx.rect(sdL, pT, sdR - sdL, pB - pT); ctx.clip();
      ctx.strokeStyle = col.supply; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.moveTo(sx, pT); ctx.lineTo(sx, pB); ctx.stroke();
      ctx.strokeStyle = col.demand; ctx.lineWidth = 2; ctx.lineCap = "round"; ctx.beginPath();
      ctx.moveTo(qx(0), yP(a - b * (0 - z))); ctx.lineTo(qx(100), yP(a - b * (100 - z))); ctx.stroke();
      ctx.restore();
      ctx.textAlign = "left"; ctx.fillStyle = col.supply; ctx.fillText("S", Math.min(sx + 4, sdR - 10), pT + 11);
      ctx.fillStyle = col.demand;
      ctx.fillText("D", qx(90), Math.max(pT + 10, Math.min(pB - 4, yP(a - b * (90 - z)) - 6)));

      var P = hp[hp.length - 1], py = yP(P);
      ctx.setLineDash([3, 3]); ctx.strokeStyle = col.muted; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(tapeR, py); ctx.lineTo(sx, py); ctx.stroke(); ctx.setLineDash([]);

      function tape(arr, y, c, t0, t1) {
        var n = Math.min(arr.length, Math.floor(tapeR - tapeL));
        ctx.save(); ctx.beginPath(); ctx.rect(tapeL, t0 - 2, tapeR - tapeL + 1, t1 - t0 + 4); ctx.clip();
        ctx.strokeStyle = c; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.beginPath();
        for (var i = arr.length - n, k = 0; i < arr.length; i++, k++) {
          var x = tapeR - (n - 1 - k), yy = y(arr[i]);
          k ? ctx.lineTo(x, yy) : ctx.moveTo(x, yy);
        }
        ctx.stroke(); ctx.restore();
      }
      tape(hp, yP, col.price, pT, pB);
      tape(hb, yB, col.slope, bT, bB);
      function dot(x, y, c, r) { ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = c; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = col.bg; ctx.stroke(); }
      dot(tapeR, py, col.price, 5); dot(sx, py, col.demand, 5); dot(tapeR, yB(b), col.slope, 4);

      readEl.textContent = "Price " + P.toFixed(1) + "  ·  shares outstanding " + Math.round(Q0) + "  ·  demand slope " + b.toFixed(2);
    }

    // ---- controls ----
    var running = opts.autoplay !== false;
    var reduce = global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce && opts.autoplay !== true) running = false;
    var visible = true, raf = 0, btn = {};
    Array.prototype.forEach.call(root.querySelectorAll("button"), function (x) { btn[x.getAttribute("data-a")] = x; });
    function label() { btn.play.textContent = running ? "Pause" : "Play"; }
    label();
    btn.play.onclick = function () { running = !running; label(); };
    btn.issue.onclick = function () {
      Qt = Qt > 50 ? 50 : 62;
      btn.issue.textContent = Qt > 50 ? "Retire shares" : "Issue shares";
    };
    btn.rw.onclick = function () {
      rw = !rw;
      btn.rw.textContent = "Beliefs: " + (rw ? "random walk" : "mean-reverting");
    };
    Array.prototype.forEach.call(inputs, function (inp) {
      var out = inp.nextElementSibling;
      inp.oninput = function () {
        var val = +inp.value;
        if (inp.getAttribute("data-k") === "flow") { flow = val; out.textContent = val; }
        else { bBar = val; out.textContent = val.toFixed(2); }
      };
    });

    function loop() {
      if (running && visible) step();
      draw();
      raf = global.requestAnimationFrame(loop);
    }
    var io = "IntersectionObserver" in global ? new IntersectionObserver(function (e) { visible = e[0].isIntersecting; }) : null;
    if (io) io.observe(root);
    var ro = "ResizeObserver" in global ? new ResizeObserver(size) : null;
    if (ro) ro.observe(box); else global.addEventListener("resize", size);
    var mq = global.matchMedia && global.matchMedia("(prefers-color-scheme: dark)");
    if (mq && mq.addEventListener) mq.addEventListener("change", readTheme);

    size();
    for (var w = 0; w < 700; w++) step();   // pre-fill the tape
    loop();

    return {
      play: function () { running = true; label(); },
      pause: function () { running = false; label(); },
      destroy: function () {
        global.cancelAnimationFrame(raf);
        if (io) io.disconnect(); if (ro) ro.disconnect();
        root.innerHTML = ""; root.classList.remove("sdt");
      }
    };
  }

  function auto() {
    var els = document.querySelectorAll("[data-sd-tape]");
    for (var i = 0; i < els.length; i++) {
      if (!els[i].__sdt) els[i].__sdt = mount(els[i], { seed: +els[i].getAttribute("data-seed") || 7 });
    }
  }
  global.SDTape = { mount: mount };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", auto); else auto();
})(window);
