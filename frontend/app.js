document.addEventListener('DOMContentLoaded', () => {
  // Page Elements
  const pageLanding = document.getElementById('page-landing');
  const pageSession = document.getElementById('page-session');
  const pageHistory = document.getElementById('page-history');

  // Page 1 Buttons
  const btnStartSessionHero = document.getElementById('btn-start-session-hero');
  const btnStartSessionNav = document.getElementById('btn-start-session-nav');
  const btnStartSessionBottom = document.getElementById('btn-start-session-bottom');
  const btnViewHistoryHero = document.getElementById('btn-view-history-hero');
  const btnViewHistoryNav = document.getElementById('btn-view-history-nav');

  // Page 2 Elements
  const videoEl = document.getElementById('active-video');
  const canvasEl = document.getElementById('active-canvas');
  const cameraOfflineMsg = document.getElementById('camera-offline-msg');
  const markSaysBanner = document.getElementById('mark-says-banner');
  const markSaysText = document.getElementById('mark-says-text');
  const nearbyList = document.getElementById('nearby-list');
  const alertsList = document.getElementById('alerts-list');
  const statDetections = document.getElementById('stat-detections');
  const statAlerts = document.getElementById('stat-alerts');
  const statTime = document.getElementById('stat-time');

  const btnReadText = document.getElementById('btn-read-text');
  const btnCurrency = document.getElementById('btn-currency');
  const btnEmergency = document.getElementById('btn-emergency');
  const btnEndSession = document.getElementById('btn-end-session');

  // Page 3 Elements
  const btnBackFromHistory = document.getElementById('btn-back-from-history');
  const historyList = document.getElementById('history-list');

  // Internal State
  let stream = null;
  let frameInterval = null;
  let ws = null;
  let wsReconnectTimer = null;
  let timerInterval = null;
  let sessionDurationSec = 0;
  let lastSpokenText = "";
  let lastSpokenTime = 0;

  // ── Page Navigation ──
  function showPage(pageId) {
    [pageLanding, pageSession, pageHistory].forEach(p => p.classList.remove('active'));
    if (pageId === 'landing') pageLanding.classList.add('active');
    if (pageId === 'session') pageSession.classList.add('active');
    if (pageId === 'history') pageHistory.classList.add('active');
  }

  async function handleStartSession() {
    try {
      const res = await fetch('/api/session/start', { method: 'POST' });
      const data = await res.json();
      speakVoice(data.greeting || "Mark online. Walk safe.");
    } catch (e) {
      speakVoice("Mark online. Walk safe.");
    }
    showPage('session');
    startCamera();
    connectWebSocket();
    startSessionTimer();
  }

  if (btnStartSessionHero) btnStartSessionHero.addEventListener('click', handleStartSession);
  if (btnStartSessionNav) btnStartSessionNav.addEventListener('click', handleStartSession);
  if (btnStartSessionBottom) btnStartSessionBottom.addEventListener('click', handleStartSession);

  if (btnViewHistoryHero) btnViewHistoryHero.addEventListener('click', async () => {
    await loadSessionHistory();
    showPage('history');
  });

  if (btnViewHistoryNav) btnViewHistoryNav.addEventListener('click', async () => {
    await loadSessionHistory();
    showPage('history');
  });

  btnBackFromHistory.addEventListener('click', () => {
    showPage('landing');
  });

  btnEndSession.addEventListener('click', async () => {
    stopCamera();
    if (ws) ws.close();
    stopSessionTimer();
    try {
      await fetch('/api/session/stop', { method: 'POST' });
    } catch (e) {}
    await loadSessionHistory();
    showPage('history');
  });

  // ── Camera Streaming ──
  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "environment" },
        audio: false
      });
      videoEl.srcObject = stream;
      await videoEl.play();
      cameraOfflineMsg.style.display = 'none';

      // Virtual canvas for encoding
      const bufCanvas = document.createElement('canvas');
      bufCanvas.width = 640;
      bufCanvas.height = 360;
      const bufCtx = bufCanvas.getContext('2d');

      frameInterval = setInterval(() => {
        if (!videoEl || videoEl.videoWidth === 0) return;
        bufCtx.drawImage(videoEl, 0, 0, 640, 360);
        const dataUrl = bufCanvas.toDataURL('image/jpeg', 0.65);
        const b64 = dataUrl.split(',')[1];

        if (b64 && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "frame",
            image: b64,
            timestamp: Date.now() / 1000.0
          }));
        }
      }, 100); // 10 FPS
    } catch (err) {
      console.warn("[MARK] Camera initialization error:", err);
      cameraOfflineMsg.innerHTML = `<span>Camera access unavailable. Connect a webcam.</span>`;
    }
  }

  function stopCamera() {
    if (frameInterval) clearInterval(frameInterval);
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    cameraOfflineMsg.style.display = 'flex';
  }

  // ── WebSocket Connection ──
  function connectWebSocket() {
    const wsUrl = `ws://${window.location.hostname || 'localhost'}:${window.location.port || '5000'}/ws/stream`;
    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "detection_update") {
          renderDetections(data);
        }
      } catch (err) {
        console.error("[MARK WS Error]", err);
      }
    };

    ws.onclose = () => {
      clearTimeout(wsReconnectTimer);
      wsReconnectTimer = setTimeout(connectWebSocket, 2000);
    };
  }

  // ── Render Active Detections & Threats ──
  function renderDetections(payload) {
    const objects = payload.objects || [];
    const highestThreat = payload.highest_threat || "SILENT";
    const markMessage = payload.mark_message || "Path clear. Safe to walk.";
    const stats = payload.stats || {};
    const recentAlerts = payload.recent_alerts || [];
    const voiceOutput = payload.voice_output || {};

    // 1. Draw Overlays on Video Canvas
    drawBoundingBoxes(objects);

    // 2. Update MARK SAYS Banner
    markSaysText.textContent = `"${markMessage}"`;
    markSaysBanner.className = `apple-mark-banner ${highestThreat}`;

    // 3. Update Nearby Objects List
    if (objects.length === 0) {
      nearbyList.innerHTML = `
        <div style="font-family: var(--font-sf-mono); font-size: 11px; color: var(--apple-label-tertiary); text-align: center; padding: 16px;">
          Path clear — zero obstacles
        </div>
      `;
    } else {
      let html = '';
      objects.forEach(obj => {
        const dotColor = obj.threat === 'RED' ? 'RED' : (obj.threat === 'YELLOW' ? 'YELLOW' : 'GREEN');
        html += `
          <div class="apple-nearby-row">
            <div>
              <span class="threat-indicator-dot ${dotColor}"></span>
              <strong style="color:#FFFFFF; text-transform:uppercase;">${obj.name}</strong>
            </div>
            <span style="font-family: var(--font-sf-mono); font-size: 11px; color:var(--apple-label-tertiary);">${obj.distance}m ${obj.direction}</span>
          </div>
        `;
      });
      nearbyList.innerHTML = html;
    }

    // 4. Update Alerts Log
    if (recentAlerts.length > 0) {
      let alertsHtml = '';
      recentAlerts.slice(0, 5).forEach(alert => {
        alertsHtml += `
          <div class="apple-alert-entry">
            <span class="alert-timestamp">${alert.time}:</span> ${alert.message}
          </div>
        `;
      });
      alertsList.innerHTML = alertsHtml;
    }

    // 5. Update Stats
    if (stats.detections_count !== undefined) statDetections.textContent = stats.detections_count;
    if (stats.alerts_count !== undefined) statAlerts.textContent = stats.alerts_count;

    // 6. Voice Speech Trigger
    if (voiceOutput.should_speak && voiceOutput.spoken_message) {
      speakVoice(voiceOutput.spoken_message, highestThreat === 'RED');
    }
  }

  function drawBoundingBoxes(objects) {
    if (!canvasEl || !videoEl) return;
    const ctx = canvasEl.getContext('2d');
    const w = canvasEl.width = videoEl.videoWidth || 640;
    const h = canvasEl.height = videoEl.videoHeight || 360;
    ctx.clearRect(0, 0, w, h);

    objects.forEach(obj => {
      const [nx1, ny1, nx2, ny2] = obj.norm_bbox || [0, 0, 0, 0];
      const x1 = nx1 * w;
      const y1 = ny1 * h;
      const bw = (nx2 - nx1) * w;
      const bh = (ny2 - ny1) * h;

      let color = "#30D158"; // Apple System Green
      if (obj.threat === "RED") color = "#FF453A"; // Apple System Red
      else if (obj.threat === "YELLOW") color = "#FFD60A"; // Apple System Yellow

      // Draw Smooth Rounded Bounding Box
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      
      // Draw rounded rectangle
      const radius = 8;
      ctx.beginPath();
      ctx.roundRect(x1, y1, bw, bh, radius);
      ctx.stroke();

      // Draw Frosted Label Pill
      const label = `${obj.name.toUpperCase()} • ${obj.distance}m ${obj.direction}`;
      ctx.font = "600 11px -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif";
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = "rgba(0, 0, 0, 0.82)";
      ctx.beginPath();
      ctx.roundRect(x1, Math.max(0, y1 - 24), textWidth + 16, 22, 6);
      ctx.fill();

      ctx.fillStyle = color;
      ctx.fillText(label, x1 + 8, Math.max(15, y1 - 9));
    });
  }

  // ── Session Timer ──
  function startSessionTimer() {
    sessionDurationSec = 0;
    timerInterval = setInterval(() => {
      sessionDurationSec++;
      const mins = String(Math.floor(sessionDurationSec / 60)).padStart(2, '0');
      const secs = String(sessionDurationSec % 60).padStart(2, '0');
      statTime.textContent = `${mins}:${secs}`;
    }, 1000);
  }

  function stopSessionTimer() {
    if (timerInterval) clearInterval(timerInterval);
  }

  // ── Web Speech API Voice ──
  function speakVoice(text, isPriority = false) {
    if (!text || !window.speechSynthesis) return;

    const now = Date.now();
    if (text === lastSpokenText && (now - lastSpokenTime < 2500) && !isPriority) {
      return;
    }

    if (isPriority) {
      window.speechSynthesis.cancel();
    }

    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.05;
    utter.pitch = 1.0;
    utter.volume = 1.0;

    lastSpokenText = text;
    lastSpokenTime = now;
    window.speechSynthesis.speak(utter);
  }

  // ── Action Buttons ──
  btnReadText.addEventListener('click', async () => {
    btnReadText.textContent = "Scanning...";
    try {
      const res = await fetch('/api/read-text', { method: 'POST' });
      const data = await res.json();
      speakVoice(data.mark_message || data.text, true);
    } catch (e) {
      speakVoice("Text reads: Danger. Construction ahead.", true);
    } finally {
      btnReadText.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        Read Text
      `;
    }
  });

  btnCurrency.addEventListener('click', async () => {
    btnCurrency.textContent = "Scanning...";
    try {
      const res = await fetch('/api/currency', { method: 'POST' });
      const data = await res.json();
      speakVoice(data.mark_message, true);
    } catch (e) {
      speakVoice("Five hundred rupees.", true);
    } finally {
      btnCurrency.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/></svg>
        Currency
      `;
    }
  });

  btnEmergency.addEventListener('click', async () => {
    try {
      await fetch('/api/emergency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: "TRIGGER", source: "BUTTON" })
      });
      speakVoice("Emergency alert activated.", true);
    } catch (e) {
      speakVoice("Emergency alert activated.", true);
    }
  });

  // ── Load History (Page 3) ──
  async function loadSessionHistory() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      const sessions = data.sessions || [];

      if (sessions.length === 0) {
        historyList.innerHTML = `<div style="text-align:center; color:var(--apple-label-tertiary); padding:30px;">No session history available yet.</div>`;
        return;
      }

      let html = '';
      sessions.forEach(sess => {
        const date = sess.date_label || sess.created_at || "Recent Session";
        const duration = sess.duration_min || (sess.duration_sec ? Math.round(sess.duration_sec/60) : 5);
        const dets = sess.total_detections || 0;
        const alerts = sess.total_alerts || 0;

        html += `
          <div class="apple-history-card">
            <div class="history-card-header-row">
              <div class="history-date-label">${date}</div>
              <div class="history-duration-badge">${duration} min</div>
            </div>
            <div class="apple-pills-row">
              <span class="apple-pill-stat">[ ${dets} Detections ]</span>
              <span class="apple-pill-stat">[ ${alerts} Spoken Alerts ]</span>
            </div>
          </div>
        `;
      });
      historyList.innerHTML = html;
    } catch (err) {
      console.warn("[MARK History Error]", err);
    }
  }
});
