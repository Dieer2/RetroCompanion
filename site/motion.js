// Motion that explains something, and nothing else (unslop, pass 9):
//  - figures draw themselves once, when they scroll into view
//  - the overlay preview on the home page plays one walkthrough step, the way the program follows a game
// Visitors who ask their system for reduced motion get the still version of both.
(function () {
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (id) { return document.getElementById(id); };

  var marked = document.querySelectorAll("[data-reveal]");
  if (marked.length && !still && "IntersectionObserver" in window) {
    document.documentElement.classList.add("js");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("seen"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -12% 0px" });
    marked.forEach(function (el) {          // what is on screen at load is shown at once, the rest when it scrolls in
      var r = el.getBoundingClientRect();
      if (r.top < innerHeight && r.bottom > 0) el.classList.add("seen"); else io.observe(el);
    });
  }

  var demo = $("demo");
  if (!demo || still) return;
  var you = $("d-you"), map = demo.querySelector(".d-map"), guide = $("d-guide");
  var first = { count: "Step 9 of 32", ch: "2 · The north", title: "Fairy Flute in Kol",
                line: "Stand exactly 4 tiles south of the bath and SEARCH", route: "Route: 6 steps" };
  var second = { count: "Step 10 of 32", ch: "2 · The north", title: "Level 10 + Half Plate",
                 line: "Level 9: RADIANT. Level 10: STOPSPELL. Half Plate costs 1000", route: "Train around Kol" };
  var timer = null, visible = false, running = false;

  function show(s) {
    $("d-count").textContent = s.count; $("d-ch").textContent = s.ch; $("d-title").textContent = s.title;
    $("d-line").textContent = s.line; $("d-route").textContent = s.route;
  }
  function place(i) {                       // i tiles walked north, out of six
    you.style.transform = "translate(-50%, -50%) translateY(" + (-i * map.clientHeight * 0.0395).toFixed(1) + "px)";
    $("d-xy").textContent = "(9, " + (12 - i) + ")";
    $("d-route").textContent = i < 6 ? "Route: " + (6 - i) + " step" + (6 - i === 1 ? "" : "s") : "You are on the tile. SEARCH";
  }
  function swap(s, then) {                  // the guide fades out, changes and rises back in
    guide.classList.add("out");
    timer = setTimeout(function () { demo.classList.remove("found"); show(s); guide.classList.remove("out"); then(); }, 260);
  }
  function wait(ms, fn) { timer = setTimeout(function () { if (visible) fn(); else running = false; }, ms); }

  function play() {
    running = true;
    show(first); place(0);
    demo.classList.remove("found");
    $("d-items").textContent = "Items: Torch, Dragon's Scale";
    var i = 0;
    var walk = function () {
      i++; place(i);
      if (i < 6) return wait(560, walk);
      wait(1100, function () {
        demo.classList.add("found");
        $("d-count").textContent = "Step 9 of 32 · done";
        $("d-items").textContent = "Items: Torch, Dragon's Scale, Fairy Flute";
        wait(1800, function () { swap(second, function () { wait(3600, function () { swap(first, play); }); }); });
      });
    };
    wait(1800, walk);
  }

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      visible = entries[0].isIntersecting && !document.hidden;
      if (visible && !running) play();
    }, { threshold: 0.4 }).observe(demo);
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { visible = false; } else { var r = demo.getBoundingClientRect(); visible = r.bottom > 0 && r.top < innerHeight; if (visible && !running) { clearTimeout(timer); play(); } }
    });
  }
})();
