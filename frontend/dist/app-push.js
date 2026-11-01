/* Notify — Web Push + voice + personal AI copy */
(function () {
  var DEFAULT_API = "https://notify-app-letm.onrender.com";
  function getApi() {
    return (localStorage.getItem("notify_api") || DEFAULT_API).replace(/\/$/, "");
  }
  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var raw = atob(base64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  async function api(path, opts) {
    opts = opts || {};
    var headers = { "Content-Type": "application/json" };
    var a = localStorage.getItem("notify_access");
    if (a && !opts.skipAuth) headers.Authorization = "Bearer " + a;
    var res = await fetch(getApi() + path, Object.assign({}, opts, { headers: headers }));
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.detail || "Request failed");
    return data;
  }
  async function enableAppPush() {
    if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      throw new Error("Use Chrome on Android for app notifications.");
    }
    var perm = await Notification.requestPermission();
    if (perm !== "granted") throw new Error("Notification permission denied");
    var vapid = await api("/api/delivery/vapid-public-key/", { skipAuth: true });
    var reg = await navigator.serviceWorker.register("./sw.js");
    await navigator.serviceWorker.ready;
    var sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapid.publicKey),
    });
    await api("/api/delivery/webpush/subscribe/", {
      method: "POST",
      body: JSON.stringify({ subscription: sub.toJSON() }),
    });
  }
  function injectButton() {
    var card = document.querySelector("#pageDelivery .card");
    if (!card || document.getElementById("enableWebPush")) return;
    var test = document.getElementById("testPush");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.id = "enableWebPush";
    btn.className = "btn btn-primary";
    btn.style.cssText = "margin-top:12px;width:100%";
    btn.innerHTML = '<span class="btn-label">Enable app notifications</span>';
    btn.onclick = async function () {
      btn.disabled = true;
      var lab = btn.querySelector(".btn-label");
      var prev = lab.textContent;
      lab.textContent = "Please wait…";
      var okEl = document.getElementById("delOk");
      var errEl = document.getElementById("delErr");
      try {
        await enableAppPush();
        if (okEl) okEl.textContent = "App notifications enabled";
        if (errEl) errEl.textContent = "";
      } catch (e) {
        if (errEl) errEl.textContent = e.message || String(e);
        if (okEl) okEl.textContent = "";
      } finally {
        btn.disabled = false;
        lab.textContent = prev;
      }
    };
    if (test && test.parentNode) test.parentNode.insertBefore(btn, test);
    else card.appendChild(btn);
  }
  function rebrand() {
    document.title = "Notify — personal AI";
    var authSub = document.querySelector("#authView .sub");
    if (authSub) authSub.textContent = "Your personal AI for reminders, weather, and news";
    var chatSub = document.querySelector("#pageChat .sub");
    if (chatSub) chatSub.textContent = "Talk or type. Reminders, snoozes, weather, news.";
    var chatH = document.querySelector("#pageChat h1");
    if (chatH) chatH.textContent = "Assistant";
  }
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(function () {});
  }
  if (!document.querySelector('link[rel="manifest"]')) {
    var l = document.createElement("link");
    l.rel = "manifest";
    l.href = "./manifest.webmanifest";
    document.head.appendChild(l);
  }
  if (!document.querySelector('script[src*="voice.js"]')) {
    var s = document.createElement("script");
    s.src = "./voice.js";
    document.body.appendChild(s);
  }
  var obs = new MutationObserver(function () {
    injectButton();
    rebrand();
  });
  obs.observe(document.body, { childList: true, subtree: true });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      injectButton();
      rebrand();
    });
  } else {
    injectButton();
    rebrand();
  }
  setInterval(function () {
    injectButton();
    rebrand();
  }, 2000);
})();
