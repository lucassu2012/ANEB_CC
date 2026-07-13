/* ============================================================================
   ANEB Probe — motion helpers (declarative, reduced-motion aware)
   Screens are STATIC-CORRECT without JS and even if a thumbnail is captured
   on frame 1 — entrance motion is a gentle *settle* from a near-final state,
   never from blank. Numbers always render their final value.
   Markup contract:
     [data-gauge value color]  on the .gauge element
        .arc     — progress <circle> (final stroke-dashoffset already set)
        .ticks   — empty <g>, filled with the bezel
     [data-stream="…1/0/s…"]   — token-stream dots
     .kbar i[data-w]           — KPI bar fills
   ==========================================================================*/
(function () {
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var C = 578.05; // circumference for r=92

  function buildTicks(g, value, color) {
    var N = 48, cx = 106, cy = 106, rin = 74, rout = 84;
    var active = Math.round((value / 100) * N);
    var ns = 'http://www.w3.org/2000/svg';
    for (var i = 0; i < N; i++) {
      var a = (i / N) * Math.PI * 2;
      var on = i < active;
      var ln = document.createElementNS(ns, 'line');
      ln.setAttribute('x1', (cx + rin * Math.cos(a)).toFixed(2));
      ln.setAttribute('y1', (cy + rin * Math.sin(a)).toFixed(2));
      ln.setAttribute('x2', (cx + rout * Math.cos(a)).toFixed(2));
      ln.setAttribute('y2', (cy + rout * Math.sin(a)).toFixed(2));
      ln.setAttribute('stroke', on ? color : 'currentColor');
      ln.setAttribute('stroke-width', '2.4');
      ln.setAttribute('stroke-linecap', 'round');
      ln.setAttribute('opacity', on ? '0.92' : '0.16');
      g.appendChild(ln);
    }
  }

  function initGauge(gauge) {
    var value = parseFloat(gauge.getAttribute('data-gauge')) || 0;
    var color = gauge.getAttribute('color') || 'var(--exc)';
    var ticks = gauge.querySelector('.ticks');
    if (ticks) buildTicks(ticks, value, color);
    var arc = gauge.querySelector('.arc');
    if (arc) {
      var target = C * (1 - value / 100);
      arc.style.strokeDashoffset = target;      // final state first (thumbnail-safe)
      if (!reduce) {
        var settleFrom = target + (C - target) * 0.5; // start ~half-drawn, settle up
        arc.style.transition = 'none';
        arc.style.strokeDashoffset = settleFrom;
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            arc.style.transition = 'stroke-dashoffset .6s var(--ease-out)';
            arc.style.strokeDashoffset = target;
          });
        });
      }
    }
  }

  function initStream(el) {
    var pat = el.getAttribute('data-stream') || '';
    el.innerHTML = '';
    [].forEach.call(pat, function (ch, i) {
      var d = document.createElement('span');
      d.className = 'tk-dot' + (ch === 's' ? ' stall' : ch === '0' ? ' dim' : '');
      if (!reduce) {
        d.style.transform = 'scale(0)';
        d.style.transitionDelay = (i * 20) + 'ms';
        requestAnimationFrame(function () { d.style.transform = 'scale(1)'; });
      }
      el.appendChild(d);
    });
  }

  function initBars() {
    document.querySelectorAll('.kbar i[data-w]').forEach(function (i) {
      var w = i.getAttribute('data-w');
      i.style.width = w;                          // final state first
      if (reduce) return;
      var start = (parseFloat(w) * 0.55).toFixed(0) + '%'; // settle from ~half
      i.style.transition = 'none';
      i.style.width = start;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          i.style.transition = 'width .6s var(--ease-out)';
          i.style.width = w;
        });
      });
    });
  }

  function boot() {
    document.querySelectorAll('[data-gauge]').forEach(initGauge);
    document.querySelectorAll('[data-stream]').forEach(initStream);
    initBars();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
