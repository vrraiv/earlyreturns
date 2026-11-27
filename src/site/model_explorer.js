/* The what-if explorer on the model page (src/site/model.py inlines this file; ELECTORAL_COLLEGE.md, section 18).

   It reads one saved run of the electoral college model, for a past election: one row per simulated election, in the
   compact form the 2026 forecast's explorer reads (uint32 win bits for contests 0 to 31, uint32 for 32 to 55, int16
   popular vote in tenths of a point; a set bit means the Democrat carries the contest). The reader sets contests for
   either side; every figure is then counted over the simulations that agree. Nothing here is a model: it only counts.

   EX (inlined by model.py) = { meta: the .json beside the draws, file: where the .bin is served, dem, rep: the two
   candidates' names, names: contest -> full name, tiles: contest -> [column, row], districts: the strip's contests }. */
(function () {
  var box = document.getElementById("ecx");
  if (!box || !window.EX) return;
  var EX = window.EX, M = EX.meta, C = M.contests, EV = M.ev, N = M.n, K = C.length;
  var $ = function (id) { return document.getElementById(id); };
  var pct = function (p) { return p == null ? "–" : p > 0.995 && p < 1 ? ">99%" : p < 0.005 && p > 0 ? "<1%" : Math.round(p * 100) + "%"; };
  var mar = function (x) { return Math.abs(x) < 0.05 ? "even" : (x > 0 ? "D+" : "R+") + Math.abs(x).toFixed(1); };
  var num = function (x) { return x.toLocaleString("en-US"); };
  var force = {};                       // contest index -> 1 (the Democrat carries it) or 0 (the Republican)
  var split = false;                    // the preset: the popular-vote winner loses the count
  var S = null;

  function load() {
    return fetch(EX.file).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.arrayBuffer(); }).then(function (buf) {
      if (buf.byteLength < 10 * N) throw new Error("truncated file");
      var s = { lo: new Uint32Array(buf, 0, N), hi: new Uint32Array(buf, 4 * N, N), pv: new Int16Array(buf, 8 * N, N), count: new Uint16Array(N) };
      for (var i = 0; i < N; i++) {
        var c = 0, a = s.lo[i], b = s.hi[i];
        for (var k = 0; k < K; k++) if (k < 32 ? (a >>> k) & 1 : (b >>> (k - 32)) & 1) c += EV[k];
        s.count[i] = c;
      }
      s.base = compute(s, {}, false);
      return s;
    });
  }

  function compute(s, f, sp) {
    var mLo = 0, vLo = 0, mHi = 0, vHi = 0, k;
    for (k in f) { k = +k; if (k < 32) { mLo |= 1 << k; if (f[k]) vLo |= 1 << k; } else { mHi |= 1 << (k - 32); if (f[k]) vHi |= 1 << (k - 32); } }
    mLo >>>= 0; vLo >>>= 0; mHi >>>= 0; vHi >>>= 0;
    var win = new Float64Array(K), hist = new Float64Array(54), m = 0, d = 0, r = 0, pvs = [], counts = [];
    for (var i = 0; i < N; i++) {
      var a = s.lo[i], b = s.hi[i];
      if (((a & mLo) >>> 0) !== vLo || ((b & mHi) >>> 0) !== vHi) continue;
      var c = s.count[i], pv = s.pv[i];
      if (sp && !((pv > 0 && c <= 268) || (pv < 0 && c >= 270))) continue;
      m++; if (c >= 270) d++; else if (c <= 268) r++;
      hist[Math.min(53, Math.floor(c / 10))]++; pvs.push(pv); counts.push(c);
      for (k = 0; k < K; k++) if (k < 32 ? (a >>> k) & 1 : (b >>> (k - 32)) & 1) win[k]++;
    }
    var med = function (x) { if (!x.length) return null; x.sort(function (p, q) { return p - q; }); return x[Math.floor(x.length / 2)]; };
    var pm = med(pvs);
    return { m: m, pD: m ? d / m : null, pR: m ? r / m : null, hist: hist, count: med(counts), pv: pm == null ? null : pm * M.pv_scale,
             p: Array.prototype.map.call(win, function (w) { return m ? w / m : null; }) };
  }

  var cls = function (p) { return p == null ? "none" : p >= 0.95 ? "d3" : p >= 0.75 ? "d2" : p >= 0.6 ? "d1" : p > 0.4 ? "toss" : p > 0.25 ? "r1" : p > 0.05 ? "r2" : "r3"; };
  var active = function () { return split || Object.keys(force).length > 0; };

  function tile(k, x, y, p) {
    var f = force[k], set = f != null, c = set ? (f ? "d3" : "r3") : cls(p);
    var state = set ? "set for " + (f ? EX.dem : EX.rep) : EX.dem + " " + pct(p);
    return '<g class="tile ' + c + (set ? " set" : "") + '" role="button" tabindex="0" data-k="' + k + '" aria-label="' + EX.names[C[k]] + ", " + EV[k] +
      " electoral vote" + (EV[k] > 1 ? "s" : "") + ": " + state + '"><rect x="' + x + '" y="' + y + '" width="44" height="44" rx="4"></rect>' +
      '<text class="st" x="' + (x + 22) + '" y="' + (y + 19) + '">' + C[k] + '</text><text class="sub" x="' + (x + 22) + '" y="' + (y + 35) + '">' +
      (set ? (f ? "D" : "R") + " set" : pct(p)) + "</text></g>";
  }

  function draw() {
    var R = compute(S, force, split), B = S.base, k, s = "";
    for (k = 0; k < K; k++) { var t = EX.tiles[C[k]]; if (t) s += tile(k, t[0] * 48 + 2, t[1] * 48 + 2, R.p[k]); }
    EX.districts.forEach(function (c, j) { s += tile(C.indexOf(c), j * 48 + 2 + 3.5 * 48, 8 * 48 + 22, R.p[C.indexOf(c)]); });
    s += '<text class="cap" x="' + (3.5 * 48 + 2) + '" y="' + (8 * 48 + 14) + '">Maine\'s and Nebraska\'s districts, one vote each</text>';
    $("ecxMap").innerHTML = '<svg viewBox="0 0 578 452" role="group" aria-label="The contests. Choose one to set its winner.">' + s + "</svg>";
    // the figures
    var delta = function (v, b) { if (v == null || !active()) return ""; var dd = Math.round(v * 100) - Math.round(b * 100); return dd === 0 ? "no change" : (dd > 0 ? "up " : "down ") + Math.abs(dd) + " pts from " + pct(b); };
    $("ecxNums").innerHTML = '<div class="exnum"><div class="l">' + EX.dem + ' reaches 270</div><div class="v">' + pct(R.pD) + '</div><div class="d">' + delta(R.pD, B.pD) + "</div></div>" +
      '<div class="exnum"><div class="l">' + EX.rep + ' reaches 270</div><div class="v">' + pct(R.pR) + '</div><div class="d">' + delta(R.pR, B.pR) + "</div></div>";
    var mt = $("ecxMatch");
    mt.className = "exmatch" + (R.m < 400 ? " warn" : "");
    mt.textContent = !active() ? "All " + num(N) + " simulations" : R.m === 0 ? "No simulation matches. Clear something to widen it."
      : num(R.m) + " of " + num(N) + " simulations match (" + pct(R.m / N) + ")" + (R.m < 400 ? ": few enough that these figures are rough" : "");
    $("ecxChips").innerHTML = '<button type="button" class="chip" id="ecxSplit" aria-pressed="' + split + '">The popular-vote winner loses</button>' +
      (active() ? '<button type="button" class="chip reset" id="ecxReset">Clear all</button>' : "");
    $("ecxSplit").onclick = function () { split = !split; draw(); };
    if ($("ecxReset")) $("ecxReset").onclick = function () { force = {}; split = false; draw(); };
    // the count's histogram: ten votes to a bar, so 270 falls between two bars
    var mx = 0, h = "", W = 540, H = 120, bw = W / 54;
    for (k = 0; k < 54; k++) mx = Math.max(mx, R.hist[k]);
    for (k = 0; k < 54; k++) if (R.hist[k]) { var bh = Math.max(1, R.hist[k] / mx * (H - 22)); h += '<rect class="' + (k >= 27 ? "d" : "r") + '" x="' + (k * bw + 0.5).toFixed(1) + '" y="' + (H - bh).toFixed(1) + '" width="' + (bw - 1).toFixed(1) + '" height="' + bh.toFixed(1) + '"></rect>'; }
    // the two labels sit on opposite sides of their lines, away from each other, whichever side the result fell
    var x270 = 27 * bw, xr = M.result.dem_count / 10 * bw, right = M.result.dem_count >= 270;
    var lab = function (x, side, t) { return '<text class="lab" x="' + (x + (side ? 4 : -4)) + '" y="8"' + (side ? "" : ' text-anchor="end"') + ">" + t + "</text>"; };
    h += '<line class="mid" x1="' + x270 + '" x2="' + x270 + '" y1="12" y2="' + H + '"></line>' + lab(x270, !right, "270") +
      '<line class="res" x1="' + xr + '" x2="' + xr + '" y1="12" y2="' + H + '"></line>' + lab(xr, right, "Result: " + M.result.dem_count) +
      '<line class="ax" x1="0" x2="' + W + '" y1="' + H + '" y2="' + H + '"></line><text class="lab" x="0" y="' + (H + 13) + '">0</text><text class="lab" x="' + W + '" y="' + (H + 13) + '" text-anchor="end">538</text>';
    $("ecxHist").innerHTML = '<svg viewBox="0 0 ' + W + " " + (H + 16) + '" role="img" aria-label="' + EX.dem + "'s electoral votes in the matching simulations. Median " + (R.count == null ? "none" : R.count) + '.">' + h + "</svg>";
    // the reading
    var set = Object.keys(force).map(function (q) { return EX.names[C[+q]] + " goes to " + (force[q] ? EX.dem : EX.rep); });
    var cond = set.length > 3 ? set.length + " contests go the way you set" : set.length > 1 ? set.slice(0, -1).join(", ") + " and " + set[set.length - 1] : set.join("");
    if (split) cond += (cond ? ", and " : "") + "the popular-vote winner loses the count";
    var txt;
    if (!active()) {
      txt = "With nothing set, these are the model's simulations for " + M.election + " as they stood: " + EX.dem + " reaches 270 in " + pct(B.pD) + " of them, with a median of " + B.count +
        " electoral votes and a popular vote of " + mar(B.pv) + ". What happened: " + EX.dem + " won " + M.result.dem_count + ". Try giving a close state to the other side and watch the rest move.";
    } else if (!R.m) {
      txt = "No simulation has that combination.";
    } else {
      txt = "In the " + num(R.m) + " simulations where " + cond + ", " + EX.dem + " reaches 270 " + pct(R.pD) + " of the time (" + pct(B.pD) + " overall), with a median of " + R.count +
        " electoral votes (" + B.count + ") and a popular vote of " + mar(R.pv) + " (" + mar(B.pv) + ").";
      var mv = [];
      for (k = 0; k < K; k++) if (force[k] == null && Math.abs(R.p[k] - B.p[k]) >= 0.04) mv.push(k);
      mv.sort(function (p, q) { return Math.abs(R.p[q] - B.p[q]) - Math.abs(R.p[p] - B.p[p]); });
      if (mv.length) txt += " The largest knock-on moves: " + mv.slice(0, 3).map(function (q) { return EX.names[C[q]] + " " + pct(B.p[q]) + " to " + pct(R.p[q]); }).join(", ") + ".";
    }
    $("ecxText").textContent = txt;
  }

  function toggle(k) { var f = force[k]; if (f == null) force[k] = 1; else if (f === 1) force[k] = 0; else delete force[k]; draw(); var g = box.querySelector('[data-k="' + k + '"]'); if (g) g.focus(); }
  $("ecxMap").addEventListener("click", function (e) { var g = e.target.closest && e.target.closest("[data-k]"); if (g) toggle(+g.getAttribute("data-k")); });
  $("ecxMap").addEventListener("keydown", function (e) { if (e.key !== "Enter" && e.key !== " ") return; var g = e.target.closest && e.target.closest("[data-k]"); if (g) { e.preventDefault(); toggle(+g.getAttribute("data-k")); } });
  load().then(function (s) { S = s; box.classList.add("live"); draw(); })
    .catch(function (e) { $("ecxMatch").textContent = "The simulations could not be loaded (" + e.message + "). The figures above are the model's own."; });
})();
