/* ============================================================
   TRIPURA JOB PULSE — site settings
   Loaded by every page. Keep this order:
     1. Settings   2. Google Analytics   3. Shared menu   4. Tracker
   ============================================================ */

window.TJP_CONFIG = {
  SUPABASE_URL: "https://rdhogmznwuqmmxhjdqed.supabase.co",
  SUPABASE_KEY: "sb_publishable_xTBTwVM75ZchO-pTH6J67Q_cEK5ud4Z",
  UPI_ID: "9643866383@ybl",
  UPI_NAME: "Tripura Job Pulse",
  LINKS: {
    WHATSAPP: "https://wa.me/919871800295",
    YOUTUBE: "https://www.youtube.com/@TripuraJobPulse",
    FACEBOOK: "https://www.facebook.com/tripurajobpulse"
  }
};


/* ====== Google Analytics ====== */
(function () {
  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=G-2RQPJ9MGRB";
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag("js", new Date());
  window.gtag("config", "G-2RQPJ9MGRB");
})();



/* ============================================================
   Shared site menu — adds the same header to every page.
   Paste this block at the END of config.js, below your settings.
   Nothing here needs editing.
   ============================================================ */
(function () {
  // Tab icon and phone home-screen icon, on every page
  var ic = document.createElement("link"); ic.rel = "icon"; ic.href = "favicon.ico";
  document.head.appendChild(ic);
  var ti = document.createElement("link"); ti.rel = "apple-touch-icon"; ti.href = "apple-touch-icon.png";
  document.head.appendChild(ti);
})();

(function () {
  // Top level menu. A group opens a small dropdown; a plain pair is a single link.
  var PUBLIC_MENU = [
    { label: "Jobs", items: [
      ["jobs.html", "Jobs in Tripura"],
      ["jobs-india.html", "Jobs within India"],
      ["jobs-remote.html", "Remote jobs"]
    ]},
    { label: "Learn", items: [
      ["study-material.html", "Study material"],
      ["mock-tests.html", "Mock tests"],
      ["learn.html", "Learn skills"],
      ["typing.html", "Typing test"],
      ["certifications.html", "Certifications"]
    ]},
    { link: ["current-affairs.html", "Current affairs"] },
    { link: ["cv.html", "CV builder"] }
  ];
  var ADMIN_LINKS = [
    ["admin-dashboard.html", "Dashboard"],
    ["admin.html", "Jobs"],
    ["admin-cards.html", "Job cards"],
    ["admin-study.html", "Study material"],
    ["admin-tests.html", "Mock tests"],
    ["admin-payments.html", "Payments"],
    ["admin-messages.html", "Messages"]
  ];
  var ICONS = "https://cdn.jsdelivr.net/npm/@tabler/icons@3.47.0/icons/outline/";

  var file = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  // The homepage has its own menu, and the test page stays distraction-free.
  if (file === "" || file === "index.html" || file === "test.html") return;

  var isAdmin = file.indexOf("admin") === 0;

  function signedIn() {
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.indexOf("sb-") === 0 && k.indexOf("auth-token") > -1 && localStorage.getItem(k)) return true;
      }
    } catch (e) {}
    return false;
  }

  function css() {
    if (document.getElementById("tjp-nav-css")) return;
    var st = document.createElement("style");
    st.id = "tjp-nav-css";
    st.textContent = [
      ".tjp-nav{position:sticky;top:0;z-index:40;background:#0E4F4C;}",
      ".tjp-nav .inner{position:relative;display:flex;align-items:center;gap:10px;max-width:1180px;margin:0 auto;padding:10px 18px;}",
      ".tjp-nav .brand{font-family:Sora,sans-serif;font-weight:700;font-size:19px;color:#F2F7F6;text-decoration:none;white-space:nowrap;display:flex;align-items:center;}",
      ".tjp-nav .brand img{height:38px;display:block;}",
      ".tjp-nav .brand span{color:#D9A13B;}",
      ".tjp-nav .menu{display:flex;align-items:center;gap:0;margin-left:auto;flex-wrap:nowrap;}",
      ".tjp-nav .menu a{color:#D8EAE6;text-decoration:none;font-size:14px;font-weight:500;padding:7px 9px;border-radius:7px;white-space:nowrap;}",
      ".tjp-nav .menu a:hover{background:rgba(255,255,255,.1);color:#fff;}",
      ".tjp-nav .menu a.on{background:rgba(255,255,255,.14);color:#fff;}",
      ".tjp-nav .menu a.cta{background:#D9A13B;color:#3A2A06;font-weight:600;}",
      ".tjp-nav .menu a.cta:hover{background:#E8B45B;}",
      ".tjp-nav .soc{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:8px;color:#D8EAE6;}",
      ".tjp-nav .soc:hover{background:rgba(255,255,255,.12);color:#fff;}",
      ".tjp-nav .soc i{display:block;width:19px;height:19px;background:currentColor;-webkit-mask:var(--i) center/contain no-repeat;mask:var(--i) center/contain no-repeat;}",
      ".tjp-group{position:relative;}",
      ".tjp-group>button{font:inherit;font-size:14px;font-weight:500;color:#D8EAE6;background:none;border:0;padding:7px 9px;border-radius:7px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;white-space:nowrap;}",
      ".tjp-group>button:hover,.tjp-group.open>button{background:rgba(255,255,255,.1);color:#fff;}",
      ".tjp-group>button.on{background:rgba(255,255,255,.14);color:#fff;}",
      ".tjp-group>button i{border:solid currentColor;border-width:0 2px 2px 0;padding:2.5px;transform:rotate(45deg);margin-top:-3px;display:inline-block;}",
      ".tjp-nav .tjp-drop{display:none;position:absolute;top:calc(100% + 6px);left:0;min-width:210px;background:#fff;border:1px solid #D3E0DC;border-radius:10px;padding:6px;box-shadow:0 14px 30px rgba(14,79,76,.18);z-index:50;}",
      ".tjp-nav .tjp-group.open .tjp-drop{display:block;}",
      ".tjp-nav .tjp-drop a{display:block;color:#142625;font-size:15px;font-weight:500;padding:9px 12px;border-radius:7px;text-decoration:none;white-space:nowrap;}",
      ".tjp-nav .tjp-drop a:hover{background:#E3EFEC;color:#0E4F4C;}",
      ".tjp-nav .tjp-drop a.on{background:#0E4F4C;color:#fff;}",
      ".tjp-nav .burger{display:none;margin-left:auto;background:none;border:1px solid rgba(255,255,255,.35);border-radius:8px;color:#fff;font-size:20px;line-height:1;padding:5px 11px;cursor:pointer;}",
      ".tjp-nav .tag{font-size:13px;font-weight:600;color:#D9A13B;border:1px solid rgba(217,161,59,.5);padding:3px 9px;border-radius:99px;}",
      ".tjp-nav .header-link{color:#F2F7F6;font:inherit;font-size:15px;background:none;border:1px solid rgba(242,247,246,.4);padding:6px 13px;border-radius:7px;cursor:pointer;text-decoration:none;}",
      ".tjp-nav .header-link:hover{border-color:#F2F7F6;}",
      ".tjp-adminrow{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;}",
      ".tjp-adminrow a{font-size:15px;font-weight:600;color:#15706B;text-decoration:none;padding:6px 12px;border-radius:7px;border:1px solid #D3E0DC;background:#fff;}",
      ".tjp-adminrow a:hover{background:#E3EFEC;}",
      ".tjp-adminrow a.on{background:#0E4F4C;border-color:#0E4F4C;color:#fff;}",
      "@media(max-width:1180px){",
      ".tjp-nav .menu{display:none;position:absolute;top:100%;left:0;right:0;background:#0E4F4C;flex-direction:column;align-items:stretch;padding:8px;gap:2px;border-top:1px solid rgba(255,255,255,.12);box-shadow:0 10px 20px rgba(0,0,0,.18);}",
      ".tjp-nav .menu.open{display:flex;}",
      ".tjp-nav .menu a{padding:12px;}",
      ".tjp-group{width:100%;}",
      ".tjp-group>button{width:100%;justify-content:space-between;padding:12px;font-size:15px;}",
      ".tjp-nav .tjp-drop{position:static;display:block;background:transparent;border:0;box-shadow:none;padding:0 0 6px 10px;min-width:0;}",
      ".tjp-nav .tjp-drop a{color:#D8EAE6;padding:10px 12px;}",
      ".tjp-nav .tjp-drop a:hover{background:rgba(255,255,255,.1);color:#fff;}",
      ".tjp-nav .tjp-drop a.on{background:rgba(255,255,255,.14);color:#fff;}",
      ".tjp-nav .menu .socwrap{display:flex;justify-content:center;gap:6px;padding:6px 0;}",
      ".tjp-nav .soc{width:46px;height:40px;}",
      ".tjp-nav .burger{display:block;}",
      "}"
    ].join("");
    document.head.appendChild(st);
  }

  function link(href, text, cls) {
    var a = document.createElement("a");
    a.href = href; a.textContent = text;
    if (cls) a.className = cls;
    if (href.toLowerCase() === file) a.className = (a.className ? a.className + " " : "") + "on";
    return a;
  }

  function socialIcon(url, name, label) {
    var a = document.createElement("a");
    a.className = "soc"; a.href = url; a.target = "_blank"; a.rel = "noopener";
    a.setAttribute("aria-label", label); a.title = label;
    var i = document.createElement("i");
    i.style.setProperty("--i", 'url("' + ICONS + name + '.svg")');
    a.appendChild(i);
    return a;
  }

  function build() {
    css();
    var old = document.querySelector("header.site-header");
    var keepLogout = document.getElementById("logout");          // admin sign-out button
    var keepAccount = document.getElementById("account-link");   // pages that track sign-in

    var header = document.createElement("header");
    header.className = "tjp-nav";
    var inner = document.createElement("div");
    inner.className = "inner";

    var brand = document.createElement("a");
    brand.className = "brand";
    brand.href = "index.html";
    brand.innerHTML = 'Tripura <span>Job Pulse</span>';
    inner.appendChild(brand);

    if (isAdmin) {
      var tag = document.createElement("span");
      tag.className = "tag"; tag.textContent = "Admin";
      inner.appendChild(tag);
    }

    var burger = document.createElement("button");
    burger.className = "burger"; burger.textContent = "☰";
    burger.setAttribute("aria-label", "Menu");
    burger.setAttribute("aria-expanded", "false");
    inner.appendChild(burger);

    var menu = document.createElement("div");
    menu.className = "menu";

    if (isAdmin) {
      ADMIN_LINKS.forEach(function (p) { menu.appendChild(link(p[0], p[1])); });
    } else {
      PUBLIC_MENU.forEach(function (entry) {
        if (entry.link) { menu.appendChild(link(entry.link[0], entry.link[1])); return; }

        var group = document.createElement("span");
        group.className = "tjp-group";
        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = entry.label;
        var caret = document.createElement("i");
        btn.appendChild(caret);
        if (entry.items.some(function (p) { return p[0].toLowerCase() === file; })) btn.className = "on";

        var drop = document.createElement("div");
        drop.className = "tjp-drop";
        entry.items.forEach(function (p) { drop.appendChild(link(p[0], p[1])); });

        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          var wasOpen = group.classList.contains("open");
          document.querySelectorAll(".tjp-group.open").forEach(function (g) { g.classList.remove("open"); });
          if (!wasOpen) group.classList.add("open");
        });

        group.appendChild(btn); group.appendChild(drop);
        menu.appendChild(group);
      });
      document.addEventListener("click", function () {
        document.querySelectorAll(".tjp-group.open").forEach(function (g) { g.classList.remove("open"); });
      });
    }

    if (isAdmin) {
      menu.appendChild(link("index.html", "View site"));
      if (keepLogout) { keepLogout.className = "header-link"; menu.appendChild(keepLogout); }
    } else {
      var L = (window.TJP_CONFIG && window.TJP_CONFIG.LINKS) || {};
      if (L.FACEBOOK || L.YOUTUBE) {
        var wrap = document.createElement("span");
        wrap.className = "socwrap";
        if (L.FACEBOOK) wrap.appendChild(socialIcon(L.FACEBOOK, "brand-facebook", "Facebook"));
        if (L.YOUTUBE) wrap.appendChild(socialIcon(L.YOUTUBE, "brand-youtube", "YouTube"));
        menu.appendChild(wrap);
      }
      if (file !== "login.html") {
        if (keepAccount) { keepAccount.className = "cta"; menu.appendChild(keepAccount); }
        else if (keepLogout) { keepLogout.className = "header-link"; menu.appendChild(keepLogout); }
        else menu.appendChild(link(signedIn() ? "profile.html" : "login.html", signedIn() ? "My profile" : "Sign in", "cta"));
      }
    }

    inner.appendChild(menu);
    header.appendChild(inner);

    burger.addEventListener("click", function () {
      var open = menu.classList.toggle("open");
      burger.setAttribute("aria-expanded", String(open));
    });
    menu.addEventListener("click", function (e) { if (e.target.tagName === "A") menu.classList.remove("open"); });

    if (old) old.replaceWith(header);
    else document.body.insertBefore(header, document.body.firstChild);

    // Admin pages carry their own row of links. Rewrite it so every page shows the same set.
    if (isAdmin) {
      var row = document.querySelector(".admin-nav");
      if (row) {
        row.className = "tjp-adminrow";
        row.innerHTML = "";
        ADMIN_LINKS.forEach(function (p) { row.appendChild(link(p[0], p[1])); });
        var site = link("index.html", "View site");
        row.appendChild(site);
        row.hidden = false;
      }
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();

/* ====== Page view tracking (for your own dashboard) ====== */
(function () {
  var cfg = window.TJP_CONFIG || {};
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_KEY) return;

  var path = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  if (path.indexOf("admin") === 0) return;            // don't count your own admin pages

  // A random id kept in this browser, so repeat visits by one person can be told apart.
  var visitor = "";
  try {
    visitor = localStorage.getItem("tjp-visitor") || "";
    if (!visitor) {
      visitor = (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
      localStorage.setItem("tjp-visitor", visitor);
    }
  } catch (e) {}

  // One record per page per 30 minutes, so a refresh doesn't inflate the numbers.
  try {
    var key = "tjp-seen-" + path;
    var last = Number(sessionStorage.getItem(key) || 0);
    if (Date.now() - last < 30 * 60 * 1000) return;
    sessionStorage.setItem(key, String(Date.now()));
  } catch (e) {}

  fetch(cfg.SUPABASE_URL + "/rest/v1/page_views", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": cfg.SUPABASE_KEY,
      "Authorization": "Bearer " + cfg.SUPABASE_KEY,
      "Prefer": "return=minimal"
    },
    body: JSON.stringify({ path: path, visitor: visitor }),
    keepalive: true
  }).catch(function () {});
})();
