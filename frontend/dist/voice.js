/* Notify — free in-app voice while the page is open (Chrome / Edge best) */
(function () {
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var canListen = !!SR;
  var canSpeak = "speechSynthesis" in window;

  function speak(text) {
    if (!canSpeak || !text) return;
    try {
      window.speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(String(text).slice(0, 700));
      u.rate = 1;
      u.lang = localStorage.getItem("notify_lang") === "ta" ? "ta-IN" : "en-IN";
      window.speechSynthesis.speak(u);
    } catch (e) {}
  }

  window.NotifyVoice = { canListen: canListen, canSpeak: canSpeak, speak: speak };

  function injectMic() {
    var form = document.getElementById("chatForm");
    var input = document.getElementById("chatInput");
    var send = document.getElementById("chatSend");
    if (!form || !input || document.getElementById("micBtn")) return;

    var mic = document.createElement("button");
    mic.type = "button";
    mic.id = "micBtn";
    mic.className = "btn btn-secondary";
    mic.style.cssText = "width:auto;min-width:48px;padding:0 12px";
    mic.title = canListen ? "Speak your command" : "Use Chrome or Edge for voice";
    mic.innerHTML = '<span class="btn-label">Mic</span>';
    mic.disabled = !canListen;

    var listening = false;
    mic.onclick = function () {
      if (!canListen || listening) return;
      listening = true;
      mic.querySelector(".btn-label").textContent = "…";
      var rec = new SR();
      rec.lang = localStorage.getItem("notify_lang") === "ta" ? "ta-IN" : "en-IN";
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      rec.onresult = function (ev) {
        listening = false;
        mic.querySelector(".btn-label").textContent = "Mic";
        input.value = ev.results[0][0].transcript;
        if (form.requestSubmit) form.requestSubmit();
        else form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
      };
      rec.onerror = function () {
        listening = false;
        mic.querySelector(".btn-label").textContent = "Mic";
      };
      rec.onend = function () {
        listening = false;
        mic.querySelector(".btn-label").textContent = "Mic";
      };
      try {
        rec.start();
      } catch (e) {
        listening = false;
        mic.querySelector(".btn-label").textContent = "Mic";
      }
    };

    if (send && send.parentNode) send.parentNode.insertBefore(mic, send);
  }

  // Speak bot replies by wrapping fetch for chat endpoint
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var url = String(args[0] || "");
    return origFetch.apply(this, args).then(function (res) {
      try {
        if (url.indexOf("/api/alerts/chat/") !== -1) {
          res.clone().json().then(function (data) {
            if (data && data.reply && data.speak !== false) speak(data.reply);
          }).catch(function () {});
        }
      } catch (e) {}
      return res;
    });
  };

  // Ensure voice.js is loaded even if index forgot the tag — self no-op
  function boot() {
    injectMic();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
  setInterval(injectMic, 2000);

  // Dynamic script include helper for pages that only load app-push.js
  if (!document.querySelector('script[src*="voice.js"]')) {
    // already executing as voice.js
  }
})();
