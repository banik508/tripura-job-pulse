/* =========================================================================
   Tripura Job Pulse — shared header and footer
   Injects the same navigation into every page. Change the menu here once.

   Each page needs three things:
     <link rel="stylesheet" href="tjp-header.css">   in <head>
     <div id="tjp-header"></div>                     where the header goes
     <div id="tjp-footer"></div>                     where the footer goes
     <script src="tjp-header.js"></script>           before </body>

   It reads social links from window.TJP_CONFIG.LINKS, so a link that is not
   configured simply does not appear rather than pointing nowhere.
   ========================================================================= */
(function () {
  "use strict";

  var ICON_BASE = "https://cdn.jsdelivr.net/npm/@tabler/icons@3.47.0/icons/outline/";
  var HERE = (location.pathname.split("/").pop() || "index.html").toLowerCase();

  /* Pages in a subfolder - /blog/a-post.html - need "../" in front of every
     link, or "jobs.html" resolves to "/blog/jobs.html" and 404s. Work out how
     deep this page sits and prefix accordingly. */
  var PARTS = location.pathname.replace(/^\/+|\/+$/g, "").split("/");
  var DEPTH = Math.max(0, PARTS.length - 1);
  var PRE = DEPTH ? new Array(DEPTH + 1).join("../") : "";
  var U = function (href) {
    if (!href) return href;
    if (/^(https?:|mailto:|tel:|#)/i.test(href)) return href;
    return PRE + href;
  };

  /* ---------- the menu, in one place ---------- */
  var MENU = [
    { label: "Jobs", items: [
      ["jobs.html",        "briefcase", "Tripura jobs",   "Government, private and remote, checked before publishing"],
      ["jobs-india.html",  "map-pin",   "Within India",   "Vacancies outside Tripura worth applying for"],
      ["jobs-remote.html", "world",     "Remote jobs",    "Work from anywhere in Tripura"],
      ["plans.html",       "check",     "Job plans",      "One-time UPI payment, no subscription"]
    ]},
    { label: "Prepare", items: [
      ["study-material.html",  "book",  "Study material",  "Modules written to the official syllabus"],
      ["mock-tests.html",      "clock", "Mock tests",      "Timed practice, marked the moment you submit"],
      ["current-affairs.html", "news",  "Current affairs", "Tripura, India and world, twice a day"],
      ["gk.html",              "bulb",  "General knowledge", "The GK that turns up in Tripura papers, plus a quick quiz"]
    ]},
    { label: "Certifications", href: "certifications.html" },
    { label: "Career Toolkit", items: [
      ["cv.html",     "file-text", "CV builder",  "A Word CV tailored to the vacancy you pick"],
      ["typing.html", "keyboard",  "Typing test", "Practice for the clerical typing stage"],
      [null, "calculator", "Salary calculator",  "Pay level to in-hand salary"],
      [null, "list-check", "Document checklist", "Exactly what to carry, per recruitment"],
      [null, "search",     "Eligibility checker","Every vacancy you actually qualify for"],
      [null, "route",      "Career roadmap",     "Your path from where you are to the post you want"]
    ]},
    { label: "Blog", href: "blog.html" }
  ];

  var SOCIAL = [
    ["FACEBOOK",  "brand-facebook",  "Facebook"],
    ["INSTAGRAM", "brand-instagram", "Instagram"],
    ["YOUTUBE",   "brand-youtube",   "YouTube"],
    ["WHATSAPP",  "brand-whatsapp",  "WhatsApp channel"]
  ];

  var FOOT = [
    ["Find work", [["jobs.html","Tripura jobs"],["jobs-india.html","Jobs within India"],
                   ["jobs-remote.html","Remote jobs"],["plans.html","Job plans"]]],
    ["Prepare",   [["study-material.html","Study material"],["mock-tests.html","Mock tests"],
                   ["current-affairs.html","Current affairs"],
                   ["gk.html","General knowledge"]]],
    ["Career Toolkit", [["cv.html","CV builder"],["typing.html","Typing test"],
                        ["certifications.html","Certifications"],["verify.html","Verify a certificate"]]],
    // privacy.html and delete-account.html are built but not uploaded yet.
    // Listing them here would put two dead links in every page footer.
    ["More",      [["index.html#contact","Post a vacancy"],["index.html#contact","Contact us"],
                   ["blog.html","Blog"],
                   ["index.html#declaration","Declaration"]]]
  ];

  var esc = function (s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  };
  var isHere = function (href) {
    return href && href.split("#")[0].toLowerCase() === HERE;
  };

  /* ---------- build the header ---------- */
  function headerHTML() {
    var out = "";
    MENU.forEach(function (m) {
      if (m.soon) {
        out += '<span class="soon-link">' + esc(m.label) + ' <span class="soon">soon</span></span>';
        return;
      }
      if (m.href) {
        out += '<a href="' + U(m.href) + '"' + (isHere(m.href) ? ' class="here"' : "") + ">" + esc(m.label) + "</a>";
        return;
      }
      var open = m.items.some(function (i) { return isHere(i[0]); });
      out += '<div class="nav-item' + (open ? " here" : "") + '">' +
             '<button class="nav-btn" type="button" aria-expanded="false">' + esc(m.label) +
             ' <span class="chev"></span></button>' +
             '<div class="drop' + (m.items.length < 4 ? " one-col" : "") + '">' +
             m.items.map(function (it) {
               var href = it[0], tag = href ? "a" : "span";
               var attrs = href ? ' href="' + U(href) + '"' : ' class="soon-item"';
               return "<" + tag + attrs + '><span class="di"><span class="icon" data-icon="' + it[1] +
                      '"></span></span><span><b>' + esc(it[2]) +
                      (href ? "" : ' <span class="soon">soon</span>') +
                      "</b><i>" + esc(it[3]) + "</i></span></" + tag + ">";
             }).join("") +
             "</div></div>";
    });

    out += '<span class="nav-social">' + SOCIAL.map(function (s) {
      return '<a class="soc-ico" data-link="' + s[0] + '" href="#" target="_blank" rel="noopener" aria-label="' +
             s[2] + '" title="' + s[2] + '"><span class="icon" data-icon="' + s[1] + '"></span></a>';
    }).join("") + "</span>";

    // Signed out, the Sign in link returns the visitor to the page they were on.
    var next = HERE && HERE !== "index.html" && HERE !== "login.html" ? "?next=" + encodeURIComponent(HERE) : "";
    out += '<a class="cta" id="account-link" href="' + U('login.html') + next + '">Sign in</a>';
    // Hidden until a session is found. Every page then has a way out.
    out += '<button class="signout" id="signout-link" type="button" hidden>Sign out</button>';

    return '<nav class="nav"><div class="inner">' +
           '<a class="brand" href="' + U("index.html") + '">Tripura <span>Job Pulse</span></a>' +
           '<button class="burger" id="tjp-burger" aria-label="Menu" aria-expanded="false">&#9776;</button>' +
           '<div class="menu" id="tjp-menu">' + out + "</div></div></nav>";
  }

  function footerHTML() {
    return '<footer class="site"><div class="fwrap"><div class="cols"><div>' +
      '<p class="brandline">Tripura <span>Job Pulse</span></p>' +
      '<p class="tag">Jobs, preparation and skills for Tripura’s job seekers, in one place.</p>' +
      '<div class="foot-social">' + SOCIAL.concat([["LINKEDIN", "brand-linkedin", "LinkedIn"]]).map(function (s) {
        return '<a data-link="' + s[0] + '" href="#" target="_blank" rel="noopener" aria-label="' + s[2] +
               '"><span class="icon" data-icon="' + s[1] + '"></span></a>';
      }).join("") + "</div></div>" +
      FOOT.map(function (c) {
        return "<div><h4>" + esc(c[0]) + "</h4>" +
               c[1].map(function (l) { return '<a href="' + U(l[0]) + '">' + esc(l[1]) + "</a>"; }).join("") +
               "</div>";
      }).join("") +
      '</div><div class="bottom"><span id="tjp-copy">© Tripura Job Pulse</span>' +
      '<span><a href="' + U("index.html") + '#declaration">Declaration</a></span></div></div></footer>';
  }

  /* ---------- paint ---------- */
  function mount() {
    var h = document.getElementById("tjp-header");
    var f = document.getElementById("tjp-footer");
    if (h) h.outerHTML = headerHTML();
    if (f) f.outerHTML = footerHTML();

    document.querySelectorAll("[data-icon]").forEach(function (s) {
      s.setAttribute("aria-hidden", "true");
      // tjp-header.css carries the icons inline. Only ask the CDN for one it
      // does not have, so a normal page makes no icon requests at all.
      var have = getComputedStyle(s).getPropertyValue("--icon").trim();
      if (!have) s.style.setProperty("--icon", 'url("' + ICON_BASE + s.dataset.icon + '.svg")');
    });

    // Social links come from config.js. An unconfigured link is removed, not left dead.
    var L = (window.TJP_CONFIG || {}).LINKS || {};
    document.querySelectorAll("[data-link]").forEach(function (a) {
      var url = L[a.dataset.link];
      if (url) a.href = url; else a.remove();
    });

    var copy = document.getElementById("tjp-copy");
    if (copy) copy.textContent = "© " + new Date().getFullYear() + " Tripura Job Pulse";

    wire();
    signedIn();
    reveals();
  }

  /* Fade sections in as they scroll into view.
     This lives here, not in a page's own module, because a module that imports
     from a CDN does not run until that CDN answers. Content must never be
     invisible because a third party is slow. */
  function reveals() {
    var items = document.querySelectorAll(".reveal, #rail");
    if (!items.length) return;
    var show = function (el) { el.classList.add("on"); };

    if (!("IntersectionObserver" in window)) {
      items.forEach(show);
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        show(e.target);
        io.unobserve(e.target);
      });
    }, { threshold: 0.14 });

    items.forEach(function (el, i) {
      if (el.classList.contains("reveal")) el.style.transitionDelay = (i % 3) * 90 + "ms";
      io.observe(el);
    });

    // Safety net: whatever happens, nothing stays hidden past three seconds.
    setTimeout(function () { items.forEach(show); }, 3000);
  }

  function wire() {
    var burger = document.getElementById("tjp-burger");
    var menu = document.getElementById("tjp-menu");
    if (burger && menu) burger.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = menu.classList.toggle("open");
      burger.setAttribute("aria-expanded", String(open));
    });

    var closeAll = function () {
      document.querySelectorAll(".nav-item.open").forEach(function (n) {
        n.classList.remove("open");
        var b = n.querySelector(".nav-btn");
        if (b) b.setAttribute("aria-expanded", "false");
      });
    };

    document.querySelectorAll(".nav-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var item = btn.closest(".nav-item");
        var was = item.classList.contains("open");
        closeAll();
        if (!was) { item.classList.add("open"); btn.setAttribute("aria-expanded", "true"); }
      });
    });

    document.addEventListener("click", closeAll);
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      closeAll();
      if (menu) menu.classList.remove("open");
    });
    document.querySelectorAll(".menu a").forEach(function (a) {
      a.addEventListener("click", function () { if (menu) menu.classList.remove("open"); closeAll(); });
    });
  }

  /* Supabase keeps its session in localStorage under sb-<ref>-auth-token.
     Reading it avoids making every page hand us its own client. If the shape
     ever changes we simply show "Sign in", which still works. */
  function signedIn() {
    var link = document.getElementById("account-link");
    if (!link) return;
    var live = false, token = null, keys = [];
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (!/^sb-.*-auth-token$/.test(k)) continue;
        keys.push(k);
        var v = JSON.parse(localStorage.getItem(k) || "{}");
        var s = v.currentSession || v;
        if (s && s.access_token && (!s.expires_at || s.expires_at * 1000 > Date.now())) {
          live = true; token = s.access_token;
        }
      }
    } catch (e) { /* private mode, blocked storage — fall through to Sign in */ }

    if (!live) return;
    link.textContent = "My profile";
    link.href = U("profile.html");

    var out = document.getElementById("signout-link");
    if (!out) return;
    out.hidden = false;

    out.addEventListener("click", function () {
      out.disabled = true;
      out.textContent = "Signing out\u2026";

      // Clear this browser first, so the person is signed out even if the
      // network call fails. Then ask Supabase to revoke the refresh token.
      var cfg = window.TJP_CONFIG || {};
      try { keys.forEach(function (k) { localStorage.removeItem(k); }); } catch (e) {}

      var done = function () { window.location.href = U("index.html"); };
      if (!cfg.SUPABASE_URL || !cfg.SUPABASE_KEY || !token) return done();

      var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
      if (ctrl) setTimeout(function () { ctrl.abort(); }, 4000);
      fetch(cfg.SUPABASE_URL + "/auth/v1/logout", {
        method: "POST",
        headers: { apikey: cfg.SUPABASE_KEY, Authorization: "Bearer " + token },
        signal: ctrl ? ctrl.signal : undefined
      }).then(done, done);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
