document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('monitor-canvas');
  const ctx = canvas.getContext('2d');
  const waitingFeed = document.getElementById('mon-waiting-feed');
  const aiModeBadge = document.getElementById('mon-ai-mode-badge');
  const riskBadge = document.getElementById('mon-risk-badge');
  const lastSpeechEl = document.getElementById('mon-last-speech');
  const eventList = document.getElementById('mon-event-list');
  const eventCountEl = document.getElementById('mon-event-count');
  const emergencyBanner = document.getElementById('mon-emergency-banner');
  const btnResolveEmergency = document.getElementById('btn-resolve-emergency');

  let eventCount = 1;
  let lastLoggedMessage = "";

  canvas.width = 640;
  canvas.height = 360;

  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host || 'localhost:5000'}/ws/stream`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "detection_update") {
          updateMonitor(payload);
        }
      } catch (e) {}
    };

    ws.onclose = () => {
      setTimeout(connectWebSocket, 2000);
    };
  }

  function updateMonitor(data) {
    if (waitingFeed) waitingFeed.style.display = 'none';

    // 1. Update AI Mode & Risk Badges
    const aiMode = data.ai_mode !== undefined ? data.ai_mode : true;
    if (aiMode) {
      aiModeBadge.className = 'badge-active';
      aiModeBadge.innerHTML = '<span style="width:8px; height:8px; border-radius:50%; background:#10b981;"></span> AI MODE: ACTIVE';
    } else {
      aiModeBadge.className = 'badge-off';
      aiModeBadge.innerHTML = '<span style="width:8px; height:8px; border-radius:50%; background:#71717a;"></span> AI MODE: PAUSED';
    }

    const threat = data.highest_threat || 'SAFE';
    riskBadge.textContent = `RISK: ${threat}`;
    if (threat === 'URGENT' || threat === 'RED') {
      riskBadge.style.color = '#ef4444';
      riskBadge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
      riskBadge.style.background = 'rgba(239, 68, 68, 0.15)';
    } else if (threat === 'CAUTION' || threat === 'YELLOW') {
      riskBadge.style.color = '#f59e0b';
      riskBadge.style.borderColor = 'rgba(245, 158, 11, 0.4)';
      riskBadge.style.background = 'rgba(245, 158, 11, 0.15)';
    } else {
      riskBadge.style.color = '#10b981';
      riskBadge.style.borderColor = 'rgba(16, 185, 129, 0.4)';
      riskBadge.style.background = 'rgba(16, 185, 129, 0.15)';
    }

    // 2. Update Last Speech
    if (data.mark_message) {
      lastSpeechEl.textContent = `"${data.mark_message}"`;
    }

    // 3. Render Canvas Stream (Image + Bounding Boxes)
    function renderBoxes() {
      const objects = data.objects || [];
      objects.forEach(obj => {
        const bbox = obj.norm_bbox || [0.2, 0.2, 0.6, 0.7];
        const x1 = bbox[0] * canvas.width;
        const y1 = bbox[1] * canvas.height;
        const x2 = bbox[2] * canvas.width;
        const y2 = bbox[3] * canvas.height;
        const w = x2 - x1;
        const h = y2 - y1;

        const isUrgent = (obj.threat === 'RED' || obj.risk_level === 'URGENT' || obj.risk_level === 'RED');
        const isCaution = (obj.threat === 'YELLOW' || obj.risk_level === 'CAUTION' || obj.risk_level === 'YELLOW');
        const strokeCol = isUrgent ? '#ef4444' : (isCaution ? '#f59e0b' : '#10b981');

        ctx.lineWidth = 3;
        ctx.strokeStyle = strokeCol;
        ctx.strokeRect(x1, y1, w, h);

        // Label Background
        const labelText = `${(obj.recognized_name || obj.name || obj.class_name || 'Object').toUpperCase()} • ${obj.distance_m || obj.distance || 2.0}m`;
        ctx.font = 'bold 12px "JetBrains Mono", monospace';
        const txtWidth = ctx.measureText(labelText).width;
        
        ctx.fillStyle = strokeCol;
        ctx.fillRect(x1, Math.max(0, y1 - 22), txtWidth + 16, 22);

        // Label Text
        ctx.fillStyle = '#000';
        ctx.fillText(labelText, x1 + 8, Math.max(15, y1 - 6));
      });
    }

    if (data.image) {
      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        renderBoxes();
      };
      img.src = 'data:image/jpeg;base64,' + data.image;
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#09090b';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      renderBoxes();
    }

    // 4. Append to Event Timeline
    if (data.mark_message && data.mark_message !== lastLoggedMessage && data.mark_message !== "Path clear.") {
      lastLoggedMessage = data.mark_message;
      addTimelineEvent(data.mark_message, threat);
    }

    // 5. Emergency Banner
    if (data.emergency && data.emergency.active) {
      emergencyBanner.style.display = 'flex';
    } else {
      emergencyBanner.style.display = 'none';
    }
  }

  function addTimelineEvent(text, threat) {
    eventCount++;
    eventCountEl.textContent = `${eventCount} events`;

    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];

    const item = document.createElement('div');
    item.className = `event-item ${threat}`;
    item.innerHTML = `
      <div class="event-time">${timeStr}</div>
      <div style="font-weight: 700; color: #fff;">${threat === 'URGENT' ? '🚨 Hazard Alert' : '🔊 Voice Directive'}</div>
      <div style="color: #e4e4e7;">${text}</div>
    `;

    eventList.insertBefore(item, eventList.firstChild);
    if (eventList.children.length > 30) {
      eventList.removeChild(eventList.lastChild);
    }
  }

  if (btnResolveEmergency) {
    btnResolveEmergency.addEventListener('click', async () => {
      await fetch('/api/emergency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: "RESOLVE" })
      });
      emergencyBanner.style.display = 'none';
    });
  }

  connectWebSocket();
});
