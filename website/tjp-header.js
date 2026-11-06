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
      ["current-affairs.html", "news",  "Current affairs", "Tripura, India and world, twice a day"]
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
    { label: "Blog", soon: true }
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
                   ["current-affairs.html","Current affairs"]]],
    ["Career Toolkit", [["cv.html","CV builder"],["typing.html","Typing test"],
                        ["certifications.html","Certifications"],["verify.html","Verify a certificate"]]],
    ["More",      [["index.html#contact","Post a vacancy"],["index.html#contact","Contact us"],
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
        out += '<a href="' + m.href + '"' + (isHere(m.href) ? ' class="here"' : "") + ">" + esc(m.label) + "</a>";
        return;
      }
      var open = m.items.some(function (i) { return isHere(i[0]); });
      out += '<div class="nav-item' + (open ? " here" : "") + '">' +
             '<button class="nav-btn" type="button" aria-expanded="false">' + esc(m.label) +
             ' <span class="chev"></span></button>' +
             '<div class="drop' + (m.items.length < 4 ? " one-col" : "") + '">' +
             m.items.map(function (it) {
               var href = it[0], tag = href ? "a" : "span";
               var attrs = href ? ' href="' + href + '"' : ' class="soon-item"';
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
    out += '<a class="cta" id="account-link" href="login.html' + next + '">Sign in</a>';

    return '<nav class="nav"><div class="inner">' +
           '<a class="brand" href="index.html">Tripura <span>Job Pulse</span></a>' +
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
               c[1].map(function (l) { return '<a href="' + l[0] + '">' + esc(l[1]) + "</a>"; }).join("") +
               "</div>";
      }).join("") +
      '</div><div class="bottom"><span id="tjp-copy">© Tripura Job Pulse</span>' +
      '<span><a href="index.html#declaration">Declaration</a></span></div></div></footer>';
  }

  /* ---------- paint ---------- */
  function mount() {
    var h = document.getElementById("tjp-header");
    var f = document.getElementById("tjp-footer");
    if (h) h.outerHTML = headerHTML();
    if (f) f.outerHTML = footerHTML();

    document.querySelectorAll("[data-icon]").forEach(function (s) {
      s.style.setProperty("--icon", 'url("' + ICON_BASE + s.dataset.icon + '.svg")');
      s.setAttribute("aria-hidden", "true");
    });
    document.documentElement.style.setProperty("--chev", 'url("' + ICON_BASE + 'chevron-down.svg")');

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
    var live = false;
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (!/^sb-.*-auth-token$/.test(k)) continue;
        var v = JSON.parse(localStorage.getItem(k) || "{}");
        var s = v.currentSession || v;
        if (s && s.access_token && (!s.expires_at || s.expires_at * 1000 > Date.now())) live = true;
      }
    } catch (e) { /* private mode, blocked storage — fall through to Sign in */ }
    if (live) { link.textContent = "My profile"; link.href = "profile.html"; }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
