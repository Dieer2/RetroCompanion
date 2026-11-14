// The ideas page: the list of suggested features, voting, sending a new one, and the sign-in
// those two need. The sign-in token of your Retro Companion account is kept in this browser
// (localStorage) until you sign out; nothing else is stored (see /privacy).
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var KEY = "rc_token", NAME = "rc_name";
  var token = localStorage.getItem(KEY) || "";
  var creating = false, after = null;
  var HEADS = [["planned", "Planned", "Decided: these get built."],
               ["open", "Open for votes", "The most wanted ones are built first."],
               ["done", "Done", "Suggested here and now in the program."]];

  function el(tag, text, cls) { var e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; }

  function api(method, path, body) {
    var h = {};
    if (body) h["Content-Type"] = "application/json";
    if (token) h.Authorization = "Bearer " + token;
    return fetch(path, { method: method, headers: h, cache: "no-store", body: body ? JSON.stringify(body) : undefined })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) { var e = new Error(d.error || "The server answered with an error"); e.status = r.status; throw e; }
          return d;
        });
      });
  }

  function signedOut() { token = ""; localStorage.removeItem(KEY); localStorage.removeItem(NAME); }

  function who() {
    var name = localStorage.getItem(NAME) || "";
    $("who").textContent = token ? "Signed in as " + name + "." : "Voting and suggesting need a Retro Companion account.";
    $("sign-out").hidden = !token;
    $("sign-in").hidden = !!token;
    $("gate").hidden = true;
  }

  function askSignIn(then) {
    after = then || null;
    $("gate").hidden = false;
    $("gate-note").textContent = "";
    $("email").focus();
  }

  function card(i) {
    var li = el("li", undefined, "idea");
    var b = el("button", undefined, "vote" + (i.voted ? " on" : ""));
    b.type = "button";
    b.appendChild(el("strong", String(i.votes)));
    b.appendChild(el("span", i.voted ? "Voted" : (i.votes === 1 ? "vote" : "votes")));
    var can = i.status === "open" || i.status === "planned";
    b.disabled = !can;
    b.setAttribute("aria-pressed", i.voted ? "true" : "false");
    b.setAttribute("aria-label", (i.voted ? "Take back your vote for " : "Vote for ") + i.title);
    if (can) b.addEventListener("click", function () { vote(i.id); });
    li.appendChild(b);
    var box = el("div");
    box.appendChild(el("h3", i.title));
    if (i.text) box.appendChild(el("p", i.text, "idea-text"));
    if (i.reply) box.appendChild(el("p", "Answer: " + i.reply, "idea-reply"));
    var meta = "Suggested by " + i.name + " · " + new Date(i.created * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    if (i.status === "new") meta += " · waiting for review, only you see it";
    if (i.status === "declined") meta += " · not taken up";
    box.appendChild(el("p", meta, "idea-meta"));
    li.appendChild(box);
    return li;
  }

  function show(d) {
    var root = $("ideas");
    root.textContent = "";
    var mine = d.ideas.filter(function (i) { return i.status === "new" || i.status === "declined"; });
    var groups = HEADS.map(function (h) { return [h[1], h[2], d.ideas.filter(function (i) { return i.status === h[0]; })]; });
    if (mine.length) groups.unshift(["Your ideas", "Each new idea is read before it shows up for everyone.", mine]);
    var any = false;
    groups.forEach(function (g) {
      if (!g[2].length) return;
      any = true;
      var sec = el("section", undefined, "idea-group");
      sec.appendChild(el("h2", g[0]));
      sec.appendChild(el("p", g[1], "sub"));
      var ul = el("ul", undefined, "idea-list");
      g[2].forEach(function (i) { ul.appendChild(card(i)); });
      sec.appendChild(ul);
      root.appendChild(sec);
    });
    if (!any) root.appendChild(el("p", "No ideas yet. Send the first one.", "status"));
    if (token && !d.signed_in) signedOut();      // the sign-in ran out
    who();
  }

  function load() {
    return api("GET", "/api/ideas").then(show).catch(function (e) {
      $("ideas").textContent = "";
      $("ideas").appendChild(el("p", "The list could not be loaded: " + e.message, "status"));
    });
  }

  function vote(id) {
    if (!token) return askSignIn(function () { vote(id); });
    api("POST", "/api/ideas/vote", { id: id }).then(load).catch(function (e) {
      if (e.status === 401) { signedOut(); who(); askSignIn(function () { vote(id); }); } else $("send-note").textContent = e.message;
    });
  }

  $("gate").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var body = { email: $("email").value.trim(), password: $("password").value };
    if (creating) body.name = $("name").value.trim();
    api("POST", creating ? "/api/register" : "/api/login", body).then(function (d) {
      token = d.token;
      localStorage.setItem(KEY, token);
      localStorage.setItem(NAME, d.user.name);
      $("password").value = "";
      var then = after; after = null;
      load().then(function () { if (then) then(); });
    }).catch(function (e) { $("gate-note").textContent = e.message; });
  });
  $("mode").addEventListener("click", function () {
    creating = !creating;
    $("name-row").hidden = !creating;
    $("name").required = creating;
    $("password").autocomplete = creating ? "new-password" : "current-password";
    $("gate-title").textContent = creating ? "Create an account" : "Sign in";
    $("gate-go").textContent = creating ? "Create account" : "Sign in";
    $("mode").textContent = creating ? "I have an account" : "Create an account";
  });
  $("sign-in").addEventListener("click", function () { askSignIn(null); });
  $("sign-out").addEventListener("click", function () {
    api("POST", "/api/logout", {}).catch(function () {}).then(function () { signedOut(); load(); });
  });
  $("send").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var go = function () {
      $("send-note").textContent = "";
      api("POST", "/api/ideas", { title: $("title").value, text: $("text").value }).then(function () {
        $("title").value = ""; $("text").value = "";
        $("send-note").textContent = "Thank you. Your idea shows up for everyone once it has been read.";
        load();
      }).catch(function (e) {
        if (e.status === 401) { signedOut(); who(); askSignIn(go); } else $("send-note").textContent = e.message;
      });
    };
    if (!token) return askSignIn(go);
    go();
  });
  who();
  load();
})();
