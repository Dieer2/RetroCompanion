// The small tools inside the guides. Every number comes from the page's own data block or tables.
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var raw = $("rc-data"), D = raw ? JSON.parse(raw.textContent) : null;
  var fmt = function (n) { return Number(n).toLocaleString("en-US"); };
  var int = function (el) { var v = parseInt(el.value, 10); return isNaN(v) ? null : v; };
  if (!D) return;

  // -- experience: level, what is left, the next spell --------------------------------
  if ($("xp-in")) {
    var W = 640, H = 280, L = 56, R = 16, T = 16, B = 36;
    var xs = function (lv) { return L + (W - L - R) * (lv - 1) / 29; };
    var ys = function (xp) { return H - B - (H - T - B) * xp / 65535; };
    $("xp-in").addEventListener("input", function () {
      var xp = int(this), out = $("xp-out"), bar = $("xp-bar"), you = $("xp-you");
      if (xp === null || xp < 0) { out.textContent = "Type the experience from your status screen"; bar.style.transform = "scaleX(0)"; return; }
      xp = Math.min(xp, 65535);
      var lv = 1;
      while (lv < 30 && xp >= D.xp[lv]) lv++;
      var text = "Level " + lv;
      if (lv < 30) {
        var lo = D.xp[lv - 1], hi = D.xp[lv];
        text += " · " + fmt(hi - xp) + " to level " + (lv + 1);
        bar.style.transform = "scaleX(" + ((xp - lo) / (hi - lo)).toFixed(3) + ")";
      } else { text += " · the top level"; bar.style.transform = "scaleX(1)"; }
      var next = Object.keys(D.spells).map(Number).filter(function (l) { return l > lv; }).sort(function (a, b) { return a - b; })[0];
      text += next ? " · next spell " + D.spells[next] + " at level " + next : " · every spell learned";
      out.textContent = text;
      if (you) {            // the point sits on the curve between the two levels
        var f = lv < 30 ? (xp - D.xp[lv - 1]) / (D.xp[lv] - D.xp[lv - 1]) : 0;
        you.setAttribute("cx", (xs(lv) + (lv < 30 ? (xs(lv + 1) - xs(lv)) * f : 0)).toFixed(1));
        you.setAttribute("cy", ys(xp).toFixed(1));
      }
    });
  }

  // -- damage: the two formulas from the game's code -------------------------------------
  if ($("d-atk")) {
    var dmg = function () {
      var atk = int($("d-atk")), edef = int($("d-edef")), eatk = int($("d-eatk")), def = int($("d-def")), parts = [];
      if (atk !== null && edef !== null) {
        var a = atk - Math.floor(edef / 2);
        parts.push("Your hit does " + (a < 2 ? "0 to 1" : Math.floor(a / 4) + " to " + Math.floor(2 * a / 4)));
      }
      if (eatk !== null && def !== null) {
        var b = eatk - Math.floor(def / 2), thr = Math.floor(eatk / 2) + 1;
        parts.push("its hit does " + (b >= thr ? Math.floor(b / 4) + " to " + Math.floor(2 * b / 4) : "0 to " + Math.floor((thr + 1) / 3)));
      }
      $("dmg-out").textContent = parts.length ? parts.join(" · ") : "Fill in the four numbers. The example in the text uses 40 and 22";
    };
    ["d-atk", "d-edef", "d-eatk", "d-def"].forEach(function (id) { $(id).addEventListener("input", dmg); });
  }

  // -- gold: dim what cannot be bought yet, or is not sold in the chosen town ------------
  if ($("g-in")) {
    var rows = [];
    document.querySelectorAll(".article table").forEach(function (t) {
      var heads = Array.prototype.map.call(t.querySelectorAll("th"), function (th) { return th.textContent.trim(); });
      var pc = heads.indexOf("Price"), sc = heads.indexOf("Sold in");
      if (pc < 0 || sc < 0) return;
      t.querySelectorAll("tbody tr").forEach(function (tr) {
        rows.push({ tr: tr, price: parseInt(tr.children[pc].textContent.replace(/,/g, ""), 10), where: tr.children[sc].textContent });
      });
    });
    var gold = function () {
      var g = int($("g-in")), town = $("g-town").value, can = 0, best = null;
      rows.forEach(function (r) {
        var sold = !town || r.where.indexOf(town) >= 0, ok = sold && (g === null || r.price <= g);
        r.tr.classList.toggle("off", !ok);
        if (ok && g !== null) { can++; if (!best || r.price > best.price) best = r; }
      });
      $("g-out").textContent = g === null
        ? (town ? "Showing what is sold in " + town : "Type your gold and the tables below dim what you cannot buy yet")
        : can ? "You can buy " + can + " of " + rows.length + " things" + (town ? " in " + town : "") + ". The dearest is the "
                + best.tr.children[0].textContent + " at " + fmt(best.price)
              : "Nothing yet" + (town ? " in " + town : "") + ". The cheapest thing costs 8";
    };
    $("g-in").addEventListener("input", gold); $("g-town").addEventListener("change", gold);
  }

  // -- the overworld chart: read a place, and find the Token from Gwaelin's reading -------
  var note = $("world-note");
  if (note) {
    var say = function (name, x, y) {
      var dx = x - D.home[0], dy = y - D.home[1];
      var ns = dy ? Math.abs(dy) + (dy > 0 ? " south" : " north") : "", ew = dx ? Math.abs(dx) + (dx > 0 ? " east" : " west") : "";
      note.textContent = name + ": " + (ns || ew ? [ns, ew].filter(Boolean).join(", ") + " of Tantegel Castle" : "where the game counts from");
    };
    document.querySelectorAll(".world .pt").forEach(function (g) {
      var go = function () {
        document.querySelectorAll(".world .pt.on").forEach(function (o) { o.classList.remove("on"); });
        g.classList.add("on"); say(g.dataset.name, +g.dataset.x, +g.dataset.y);
      };
      g.addEventListener("click", go); g.addEventListener("focus", go); g.addEventListener("mouseenter", go);
    });
  }
  if ($("l-ns")) {
    var love = function () {
      var ns = int($("l-ns")), ew = int($("l-ew")), you = $("love-you");
      if (ns === null || ew === null) { $("l-out").textContent = "Type what Gwaelin's Love tells you and see how far the Token is"; if (you) you.setAttribute("visibility", "hidden"); return; }
      var x = D.home[0] + ($("l-ewd").value === "east" ? ew : -ew), y = D.home[1] + ($("l-nsd").value === "south" ? ns : -ns);
      if (x < 0 || x > 119 || y < 0 || y > 119) { $("l-out").textContent = "That spot is off the map. The world is 120 tiles each way"; if (you) you.setAttribute("visibility", "hidden"); return; }
      var dx = D.token[0] - x, dy = D.token[1] - y;
      $("l-out").textContent = !dx && !dy ? "You are standing on it. Use SEARCH"
        : "Walk " + [dy ? Math.abs(dy) + (dy > 0 ? " south" : " north") : "", dx ? Math.abs(dx) + (dx > 0 ? " east" : " west") : ""].filter(Boolean).join(" and ") + " to reach the Token";
      if (you) { you.setAttribute("transform", "translate(" + (x * 4 + 2) + " " + (y * 4 + 2) + ")"); you.setAttribute("visibility", "visible"); }
    };
    ["l-ns", "l-ew"].forEach(function (id) { $(id).addEventListener("input", love); });
    ["l-nsd", "l-ewd"].forEach(function (id) { $(id).addEventListener("change", love); });
  }

  // -- the walkthrough: tick steps off, kept on this device ------------------------------
  var lists = document.querySelectorAll("ol.steps");
  if (lists.length) {
    var KEY = "rc-dw-steps", done = {};
    try { done = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
    var items = [], head = document.createElement("div");
    head.className = "tool progress";
    head.innerHTML = '<p class="out" id="st-out"></p><div class="meter"><span id="st-bar"></span></div><button type="button" class="btn quiet" id="st-reset">Start over</button>';
    lists[0].parentNode.insertBefore(head, lists[0].previousElementSibling);
    var paint = function () {
      var n = items.filter(function (it) { return it.box.checked; }).length;
      $("st-out").textContent = n ? n + " of " + items.length + " steps done" + (n === items.length ? ". The game is finished" : "") : "Tick a step when you finish it. Your place is kept on this device";
      $("st-bar").style.transform = "scaleX(" + (n / items.length).toFixed(3) + ")";
      try { localStorage.setItem(KEY, JSON.stringify(done)); } catch (e) {}
    };
    lists.forEach(function (ol) {
      var n = ol.start || 1;
      ol.querySelectorAll("li").forEach(function (li) {
        var num = n++, box = document.createElement("input"), label = document.createElement("label");
        box.type = "checkbox"; box.checked = !!done[num]; box.setAttribute("aria-label", "Step " + num + " done");
        while (li.firstChild) label.appendChild(li.firstChild);
        li.appendChild(box); li.appendChild(label); li.classList.toggle("done", box.checked);
        label.addEventListener("click", function () { box.click(); });
        box.addEventListener("change", function () { if (box.checked) done[num] = 1; else delete done[num]; li.classList.toggle("done", box.checked); paint(); });
        items.push({ box: box, li: li });
      });
    });
    $("st-reset").addEventListener("click", function () {
      done = {}; items.forEach(function (it) { it.box.checked = false; it.li.classList.remove("done"); }); paint();
    });
    paint();
  }
})();
