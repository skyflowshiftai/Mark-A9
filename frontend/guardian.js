document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('guardian-canvas');
  const ctx = canvas ? canvas.getContext('2d', { alpha: false }) : null;
  const feedWaitingOverlay = document.getElementById('feed-waiting-overlay');
  const camStatusChip = document.getElementById('cam-status-chip');
  const aiModeTag = document.getElementById('ai-mode-tag');
  const statSituation = document.getElementById('stat-situation');
  const statThreat = document.getElementById('stat-threat');
  const statPath = document.getElementById('stat-path');
  const statObjCount = document.getElementById('stat-obj-count');
  const latestVoiceMsg = document.getElementById('latest-voice-msg');
  const timelineList = document.getElementById('timeline-list');
  const eventCounter = document.getElementById('event-counter');
  const connectionBadge = document.getElementById('connection-badge');
  const hudTelemetry = document.getElementById('hud-telemetry');
  const sosBanner = document.getElementById('guardian-sos-banner');
  const sessionTag = document.getElementById('session-tag');

  // Set internal resolution
  if (canvas) {
    canvas.width = 640;
    canvas.height = 360;
  }

  // Session ID from URL params or default
  const urlParams = new URLSearchParams(window.location.search);
  const sessionId = urlParams.get('session') || 'DEMO-01';
  if (sessionTag) sessionTag.textContent = sessionId;

  let totalEvents = 0;
  let hasReceivedFirstFrame = false;
  let lastLoggedMsg = "";

  // Dedicated Ultra-Low-Latency Rendering Buffer
  let latestData = null;
  let isRafPending = false;
  const sharedImg = new Image();
  let latestTimestamp = 0;
  let imgDecoding = false;

  // WebSocket Connection
  let ws = null;
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host || 'localhost:5000'}/ws/stream`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      if (connectionBadge) {
        connectionBadge.textContent = '● CONNECTED TO SESSION';
        connectionBadge.style.color = '#10b981';
        connectionBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'detection_update' || data.objects !== undefined) {
          // Reject stale / out-of-order WebSocket packets
          if (data.timestamp && data.timestamp < latestTimestamp) {
            return;
          }
          if (data.timestamp) latestTimestamp = data.timestamp;

          latestData = data;
          updateGuardianDOM(data);
          scheduleRender();
        }
      } catch (err) {
        console.error('Guardian message error:', err);
      }
    };

    ws.onclose = () => {
      if (connectionBadge) {
        connectionBadge.textContent = '○ RECONNECTING...';
        connectionBadge.style.color = '#f59e0b';
        connectionBadge.style.borderColor = 'rgba(245, 158, 11, 0.3)';
      }
      setTimeout(connectWebSocket, 2000);
    };
  }

  connectWebSocket();

  function updateGuardianDOM(data) {
    const objects = data.objects || [];
    const threat = data.highest_threat || 'SILENT';
    const aiMode = data.ai_mode !== false;
    const markMsg = data.mark_message || 'Path clear.';
    const stats = data.stats || {};
    const emergency = data.emergency || {};

    // 1. Telemetry HUD
    if (hudTelemetry && stats.fps !== undefined) {
      hudTelemetry.textContent = `FPS: ${stats.fps} • LATENCY: ~${stats.latency_ms || 12}ms`;
    }

    // 2. AI Mode & State Pills
    if (aiModeTag) {
      aiModeTag.textContent = aiMode ? 'AI: ON' : 'AI: PAUSED';
      aiModeTag.style.color = aiMode ? '#10b981' : '#71717a';
    }

    if (statObjCount) statObjCount.textContent = objects.length;

    if (statThreat) {
      statThreat.textContent = threat;
      if (threat === 'RED' || threat === 'URGENT' || threat === 'CRITICAL') statThreat.style.color = '#ef4444';
      else if (threat === 'YELLOW' || threat === 'CAUTION') statThreat.style.color = '#f59e0b';
      else statThreat.style.color = '#10b981';
    }

    if (statPath) {
      const isBlocked = objects.some(o => o.distance_m <= 2.5 && (o.spatial_sector === 'CENTER' || o.direction === 'CENTER'));
      statPath.textContent = isBlocked ? 'BLOCKED' : 'CLEAR';
      statPath.style.color = isBlocked ? '#ef4444' : '#10b981';
    }

    if (statSituation) {
      if (objects.some(o => (o.class_name || '').toLowerCase() === 'person')) {
        statSituation.textContent = 'PERSON PRESENT';
        statSituation.style.color = '#38bdf8';
      } else if (objects.length > 0) {
        statSituation.textContent = 'OBSTACLE PRESENT';
        statSituation.style.color = '#f59e0b';
      } else {
        statSituation.textContent = 'CLEAR';
        statSituation.style.color = '#10b981';
      }
    }

    // 3. Spoken Voice Message
    if (latestVoiceMsg && markMsg) {
      latestVoiceMsg.textContent = `"${markMsg}"`;
    }

    // 4. Emergency State
    if (sosBanner) {
      if (emergency.is_active || threat === 'CRITICAL') {
        sosBanner.style.display = 'flex';
      } else {
        sosBanner.style.display = 'none';
      }
    }

    // 5. Timeline Addition (Deduplicated)
    if (markMsg && markMsg !== 'AI MODE PAUSED' && markMsg !== 'Path clear.' && markMsg !== lastLoggedMsg && timelineList) {
      lastLoggedMsg = markMsg;
      totalEvents++;
      if (eventCounter) eventCounter.textContent = `${totalEvents} EVENTS`;

      const item = document.createElement('div');
      item.className = `timeline-item ${threat}`;
      item.innerHTML = `
        <div class="timeline-time">${new Date().toLocaleTimeString()} • ${threat}</div>
        <div style="font-weight: 700; color: #fff;">${markMsg}</div>
      `;
      timelineList.prepend(item);
      if (timelineList.children.length > 30) timelineList.removeChild(timelineList.lastChild);
    }
  }

  function scheduleRender() {
    if (!isRafPending) {
      isRafPending = true;
      requestAnimationFrame(renderFrame);
    }
  }

  function renderFrame() {
    isRafPending = false;
    if (!latestData || !canvas || !ctx) return;

    const data = latestData;
    const objects = data.objects || [];
    const imageB64 = data.image;
    const w = 640;
    const h = 360;

    function drawOverlays() {
      (objects || []).forEach(obj => {
        const [nx1, ny1, nx2, ny2] = obj.norm_bbox || [0, 0, 0, 0];
        const x1 = nx1 * w;
        const y1 = ny1 * h;
        const bw = Math.max(10, (nx2 - nx1) * w);
        const bh = Math.max(10, (ny2 - ny1) * h);

        const name = (obj.recognized_name || obj.class_name || obj.name || 'Object').toUpperCase();
        const threat = (obj.risk_level || obj.threat || 'LOW').toUpperCase();
        const trackId = obj.track_id || obj.id || 1;
        const conf = obj.confidence ? Math.round(obj.confidence * 100) : 85;
        const distStr = (obj.distance_info && obj.distance_info.distance_m) ? `${obj.distance_info.distance_m}m` : (obj.proximity || '2.0m');
        const motionStr = obj.motion_state || (obj.motion ? obj.motion.state : 'STATIONARY');

        let strokeCol = '#10b981';
        let bgCol = 'rgba(16, 185, 129, 0.15)';
        if (threat === 'RED' || threat === 'URGENT' || threat === 'CRITICAL') {
          strokeCol = '#ef4444';
          bgCol = 'rgba(239, 68, 68, 0.2)';
        } else if (threat === 'YELLOW' || threat === 'CAUTION') {
          strokeCol = '#f59e0b';
          bgCol = 'rgba(245, 158, 11, 0.15)';
        } else if (threat === 'AWARENESS') {
          strokeCol = '#38bdf8';
          bgCol = 'rgba(56, 189, 248, 0.15)';
        }

        // Bounding Box
        ctx.fillStyle = bgCol;
        ctx.fillRect(x1, y1, bw, bh);

        ctx.strokeStyle = strokeCol;
        ctx.lineWidth = 2.5;
        ctx.strokeRect(x1, y1, bw, bh);

        // Tag badge
        const label = `#0${trackId} ${name} (${conf}%) • ${distStr} • ${motionStr}`;
        ctx.font = 'bold 11px "JetBrains Mono", monospace';
        const tw = ctx.measureText(label).width;

        ctx.fillStyle = 'rgba(0, 0, 0, 0.90)';
        ctx.fillRect(x1, Math.max(0, y1 - 22), tw + 14, 20);

        ctx.strokeStyle = strokeCol;
        ctx.lineWidth = 1;
        ctx.strokeRect(x1, Math.max(0, y1 - 22), tw + 14, 20);

        ctx.fillStyle = strokeCol;
        ctx.fillText(label, x1 + 6, Math.max(14, y1 - 8));
      });
    }

    if (imageB64) {
      if (feedWaitingOverlay && feedWaitingOverlay.style.display !== 'none') {
        feedWaitingOverlay.style.display = 'none';
      }
      if (camStatusChip) {
        camStatusChip.textContent = '● LIVE USER CAMERA';
        camStatusChip.style.color = '#10b981';
      }
      hasReceivedFirstFrame = true;

      if (!imgDecoding) {
        imgDecoding = true;
        sharedImg.onload = () => {
          imgDecoding = false;
          ctx.drawImage(sharedImg, 0, 0, w, h);
          drawOverlays();
        };
        sharedImg.onerror = () => {
          imgDecoding = false;
        };
        sharedImg.src = 'data:image/jpeg;base64,' + imageB64;
      } else {
        // Overlay directly if decode in progress
        drawOverlays();
      }
    } else {
      if (!hasReceivedFirstFrame && feedWaitingOverlay) {
        feedWaitingOverlay.style.display = 'flex';
      }
      ctx.fillStyle = '#09090b';
      ctx.fillRect(0, 0, w, h);
      drawOverlays();
    }
  }
});
