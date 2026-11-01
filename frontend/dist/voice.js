/* Notify — free in-app voice (Web Speech API) while the page is open */
(function () {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canListen = !!SR;
  const canSpeak = "speechSynthesis" in window;

  function speak(text) {
    if (!canSpeak || !text) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text).slice(0, 600));
      u.rate = 1;
      u.lang = (localStorage.getItem("notify_lang") === "ta") ? "ta-IN" : "en-IN";
      window.speechSynthesis.speak(u);
    } catch (e) {}
  }

  window.NotifyVoice = {
    canListen,
    canSpeak,
    speak,
    listenOnce: function (onText, onError) {
      if (!canListen) {
        onError && onError(new Error("Voice input needs Chrome or Edge"));
        return null;
      }
      const rec = new SR();
      rec.lang = (localStorage.getItem("notify_lang") === "ta") ? "ta-IN" : "en-IN";
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      rec.onresult = function (ev) {
        const t = ev.results[0][0].transcript;
        onText && onText(t);
      };
      rec.onerror = function (ev) {
        onError && onError(new Error(ev.error || "listen failed"));
      };
      try {
        rec.start();
      } catch (e) {
        onError && onError(e);
      }
      return rec;
    },
  };

  function enhanceChat() {
    const form = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");
    if (!form || !input || document.getElementById("micBtn")) return;

    const mic = document.createElement("button");
    mic.type = "button";
    mic.id = "micBtn";
    mic.className = "btn btn-secondary";
    mic.style.cssText = "width:auto;min-width:48px;padding:0 12px";
    mic.title = canListen ? "Speak" : "Voice not supported in this browser";
    mic.innerHTML = '<span class="btn-label">Mic</span>';
    mic.disabled = !canListen;

    let listening = false;
    mic.onclick = function () {
      if (!canListen || listening) return;
      listening = true;
      mic.querySelector(".btn-label").textContent = "…";
      window.NotifyVoice.listenOnce(
        function (text) {
          listening = false;
          mic.querySelector(".btn-label").textContent = "Mic";
          input.value = text;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          // auto-send
          form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
        },
        function () {
          listening = false;
          mic.querySelector(".btn-label").textContent = "Mic";
        }
      );
    };

    const send = document.getElementById("chatSend");
    if (send && send.parentNode) send.parentNode.insertBefore(mic, send);

    // Speak bot replies when API returns speak:true — hook fetch via custom event
    window.addEventListener("notify-bot-reply", function (ev) {
      const d = ev.detail || {};
      if (d.speak && d.reply) speak(d.reply);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhanceChat);
  else enhanceChat();
  setInterval(enhanceChat, 1500);
})();
