// Counts this page view on our own server. No cookie, and no address is stored (see /privacy).
// A link like /?ref=reddit names where a visitor came from; otherwise the referring site is used.
(function () {
  try {
    var q = new URLSearchParams(location.search);
    var ref = q.get("ref") || q.get("utm_source") || document.referrer || "";
    fetch("/api/hit", { method: "POST", keepalive: true, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page: location.pathname, ref: ref }) }).catch(function () {});
  } catch (e) {}
})();
