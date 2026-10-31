/* Notify — Web Push / installable app notifications */
(function () {
  const DEFAULT_API = "https://notify-app-letm.onrender.com";
  function getApi() {
    return (localStorage.getItem("notify_api") || DEFAULT_API).replace(/\/$/, "");
  }
  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  async function api(path, opts) {
    opts = opts || {};
    const headers = { "Content-Type": "application/json" };
    const a = localStorage.getItem("notify_access");
    if (a && !opts.skipAuth) headers.Authorization = "Bearer " + a;
    const res = await fetch(getApi() + path, { ...opts, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Request failed");
    return data;
  }
  async function enableAppPush() {
    if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      throw new Error("Use Chrome on Android for app notifications.");
    }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") throw new Error("Notification permission denied");
    const vapid = await api("/api/delivery/vapid-public-key/", { skipAuth: true });
    const reg = await navigator.serviceWorker.register("./sw.js");
    await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapid.publicKey),
    });
    await api("/api/delivery/webpush/subscribe/", {
      method: "POST",
      body: JSON.stringify({ subscription: sub.toJSON() }),
    });
  }
  function injectButton() {
    const card = document.querySelector("#pageDelivery .card");
    if (!card || document.getElementById("enableWebPush")) return;
    const test = document.getElementById("testPush");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "enableWebPush";
    btn.className = "btn btn-primary";
    btn.style.cssText = "margin-top:12px;width:100%";
    btn.innerHTML = '<span class="btn-label">Enable app notifications</span>';
    btn.onclick = async function () {
      btn.disabled = true;
      const lab = btn.querySelector(".btn-label");
      const prev = lab.textContent;
      lab.textContent = "Please wait…";
      const okEl = document.getElementById("delOk");
      const errEl = document.getElementById("delErr");
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
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(function () {});
  }
  // manifest link
  if (!document.querySelector('link[rel="manifest"]')) {
    const l = document.createElement("link");
    l.rel = "manifest";
    l.href = "./manifest.webmanifest";
    document.head.appendChild(l);
  }
  const obs = new MutationObserver(injectButton);
  obs.observe(document.body, { childList: true, subtree: true });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", injectButton);
  else injectButton();
  setInterval(injectButton, 2000);
})();
