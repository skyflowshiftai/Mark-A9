document.addEventListener('DOMContentLoaded', () => {
  // Navigation Tabs
  const tabLive = document.getElementById('tab-live');
  const tabGuardian = document.getElementById('tab-guardian');
  const tabHistory = document.getElementById('tab-history');

  const viewLive = document.getElementById('view-live');
  const viewGuardian = document.getElementById('view-guardian');
  const viewHistory = document.getElementById('view-history');
  const historyContainer = document.getElementById('history-container');
  const guardianCanvas = document.getElementById('guardian-canvas');

  // Camera & Canvas
  const videoEl = document.getElementById('active-video');
  const canvasEl = document.getElementById('active-canvas');
  const ctx = canvasEl ? canvasEl.getContext('2d') : null;
  const cameraOfflineMsg = document.getElementById('camera-offline-msg');
  const btnToggleCamera = document.getElementById('btn-toggle-camera');
  const btnToggleLang = document.getElementById('btn-toggle-lang');
  const btnToggleAiMode = document.getElementById('btn-toggle-ai-mode');
  const hudLatency = document.getElementById('hud-latency');
  const hudCamStatus = document.getElementById('hud-cam-status');

  // Emergency SOS Elements
  const emergencyActiveBanner = document.getElementById('emergency-active-banner');
  const emergencyCallStatusText = document.getElementById('emergency-call-status-text');
  const btnResolveEmergency = document.getElementById('btn-resolve-emergency');

  // Ensure canvas internal coordinate space is permanently fixed
  if (canvasEl) {
    canvasEl.width = 640;
    canvasEl.height = 360;
  }
  if (guardianCanvas) {
    guardianCanvas.width = 640;
    guardianCanvas.height = 360;
  }

  // Sidebar Tracking & World State
  const trackingList = document.getElementById('tracking-list');
  const envTotalTag = document.getElementById('env-total-tag');

  // The ONE Microphone Control
  const voiceCompanionCard = document.getElementById('voice-companion-card');
  const voiceMicBadge = document.getElementById('voice-mic-badge');
  const btnTalkMark = document.getElementById('btn-talk-mark');
  const micIcon = document.getElementById('mic-icon');
  const micLabel = document.getElementById('mic-label');
  const transcriptYou = document.getElementById('transcript-you');
  const transcriptMark = document.getElementById('transcript-mark');

  // Intelligence Card Elements
  const intelligenceCard = document.getElementById('intelligence-card');
  const intelRiskLevel = document.getElementById('intel-risk-level');
  const intelPathStatus = document.getElementById('intel-path-status');
  const intelLastInstruction = document.getElementById('intel-last-instruction');
  const intelDecisionPill = document.getElementById('intel-decision-pill');

  // State Management
  let stream = null;
  let frameTimer = null;
  let ws = null;
  let isCameraActive = false;
  let isAiMode = true;
  let currentLanguage = 'te-IN'; // Default Telugu
  let isFrameInFlight = false;
  let lastFrameSentTime = 0;

  // DOM State Caching (prevents layout reflow / DOM thrashing)
  let cachedThreat = "";
  let cachedObjectsKey = "";
  let cachedRiskClass = "";

  // ── 1. SINGLETON MICROPHONE CONTROLLER & STATE MACHINE ──
  // State Machine: IDLE | LISTENING | TRANSCRIBING | PROCESSING (THINKING) | SPEAKING | ERROR
  let micState = 'IDLE';
  let speechRecognizer = null;
  let recognitionActive = false;
  let isSpeaking = false;

  function setMicState(state, customLabel = '') {
    micState = state;
    if (!btnTalkMark || !voiceCompanionCard) return;

    btnTalkMark.className = `btn-talk-mark ${state}`;
    voiceCompanionCard.className = `app-voice-companion-card ${state}`;

    if (state === 'IDLE') {
      micIcon.textContent = '🎙️';
      micLabel.textContent = 'TALK TO MARK';
      if (voiceMicBadge) {
        voiceMicBadge.textContent = 'PUSH TO TALK';
        voiceMicBadge.style.color = '#38bdf8';
      }
    } else if (state === 'LISTENING') {
      micIcon.textContent = '🔴';
      micLabel.textContent = 'MARK IS LISTENING... (HEARING YOU)';
      if (voiceMicBadge) {
        voiceMicBadge.textContent = customLabel || 'LISTENING...';
        voiceMicBadge.style.color = '#ef4444';
      }
    } else if (state === 'TRANSCRIBING') {
      micIcon.textContent = '✍️';
      micLabel.textContent = 'TRANSCRIBING VOICE...';
      if (voiceMicBadge) {
        voiceMicBadge.textContent = 'CAPTURING SPEECH';
        voiceMicBadge.style.color = '#f59e0b';
      }
    } else if (state === 'PROCESSING') {
      micIcon.textContent = '◌';
      micLabel.textContent = 'MARK IS THINKING... (EVALUATING WORLD)';
      if (voiceMicBadge) {
        voiceMicBadge.textContent = 'CHECKING WORLD STATE';
        voiceMicBadge.style.color = '#38bdf8';
      }
    } else if (state === 'SPEAKING') {
      micIcon.textContent = '🔊';
      micLabel.textContent = 'MARK IS SPEAKING...';
      if (voiceMicBadge) {
        voiceMicBadge.textContent = 'SPEAKING';
        voiceMicBadge.style.color = '#10b981';
      }
    } else if (state === 'ERROR') {
      micIcon.textContent = '⚠️';
      micLabel.textContent = 'MIC UNAVAILABLE';
      if (voiceMicBadge) {
        voiceMicBadge.textContent = 'PERMISSION NEEDED';
        voiceMicBadge.style.color = '#f59e0b';
      }
    }
  }

  function playAudioAlert(text, priority = "NORMAL", isInterrupt = false, onEndCallback = null) {
    if (!text || !window.speechSynthesis) return;

    if (isInterrupt) {
      window.speechSynthesis.cancel();
    }

    isSpeaking = true;
    if (speechRecognizer && recognitionActive) {
      try { speechRecognizer.abort(); } catch (e) {}
    }

    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = currentLanguage;
    utter.rate = (priority === 'CRITICAL' || priority === 'URGENT' || priority === 'critical') ? 1.15 : 1.0;
    utter.pitch = 1.0;

    setMicState('SPEAKING');

    utter.onend = () => {
      isSpeaking = false;
      if (micState === 'SPEAKING') setMicState('IDLE');
      if (onEndCallback) onEndCallback();
    };

    utter.onerror = () => {
      isSpeaking = false;
      if (micState === 'SPEAKING') setMicState('IDLE');
    };

    window.speechSynthesis.speak(utter);
  }

  function setupSpeechRecognizer() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      console.warn("[MIC] SpeechRecognition not supported in browser.");
      setMicState('ERROR');
      return;
    }

    if (speechRecognizer) return; // Prevent duplicate instantiation

    speechRecognizer = new SpeechRec();
    speechRecognizer.continuous = false;
    speechRecognizer.interimResults = true;
    speechRecognizer.lang = currentLanguage;

    speechRecognizer.onstart = () => {
      recognitionActive = true;
      setMicState('LISTENING');
    };

    speechRecognizer.onresult = (event) => {
      if (isSpeaking) return; // Prevent self-transcription loopback

      let interim = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
        else interim += event.results[i][0].transcript;
      }

      if (interim && transcriptYou) {
        setMicState('TRANSCRIBING');
        transcriptYou.textContent = `"${interim}..."`;
      }

      if (finalTranscript) {
        transcriptYou.textContent = `"${finalTranscript}"`;
        triggerVoiceQuery(finalTranscript);
      }
    };

    speechRecognizer.onerror = (e) => {
      recognitionActive = false;
      if (e.error === 'not-allowed') {
        setMicState('ERROR');
        if (transcriptMark) transcriptMark.textContent = '"మైక్రోఫోన్ అనుమతి ఇవ్వండి సర్."';
      } else if (micState === 'LISTENING' || micState === 'TRANSCRIBING') {
        setMicState('IDLE');
      }
    };

    speechRecognizer.onend = () => {
      recognitionActive = false;
      if (micState === 'LISTENING' || micState === 'TRANSCRIBING') {
        setMicState('IDLE');
      }
    };
  }

  async function startListeningSession() {
    if (window.speechSynthesis && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      isSpeaking = false;
    }

    try {
      // Explicit permission verification
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioStream.getTracks().forEach(t => t.stop()); // close probe track
      }
    } catch (err) {
      console.warn("[MIC Permission Denied]", err);
      setMicState('ERROR');
      if (transcriptMark) transcriptMark.textContent = '"మైక్రోఫోన్ అనుమతి ఇవ్వండి సర్."';
      return;
    }

    if (!speechRecognizer) setupSpeechRecognizer();
    if (!speechRecognizer) return;

    try {
      setMicState('LISTENING');
      speechRecognizer.start();
    } catch (e) {
      try {
        speechRecognizer.abort();
        setTimeout(() => speechRecognizer.start(), 150);
      } catch (err) {}
    }
  }

  // The Single Mic Button Click Handler
  if (btnTalkMark) {
    btnTalkMark.addEventListener('click', () => {
      // User Interruption: Cancel any active speech immediately
      if (window.speechSynthesis && window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        isSpeaking = false;
      }

      if (micState === 'LISTENING' || micState === 'TRANSCRIBING') {
        if (speechRecognizer) speechRecognizer.stop();
      } else {
        const promptCue = currentLanguage.startsWith("te") ? "చెప్పండి సర్." : "Yes sir, I'm listening.";
        playAudioAlert(promptCue, "NORMAL", true, () => {
          startListeningSession();
        });
      }
    });
  }

  window.triggerVoiceQuery = async (queryText) => {
    if (!queryText || queryText.trim() === "") {
      const fallbackMsg = currentLanguage.startsWith("te") ? "సర్, మీ మాట నాకు వినిపించలేదు. మరోసారి చెప్పండి." : "Sir, I couldn't hear clearly. Please speak again.";
      if (transcriptMark) transcriptMark.textContent = `"${fallbackMsg}"`;
      playAudioAlert(fallbackMsg, "NORMAL", true);
      return;
    }

    setMicState('PROCESSING');
    if (transcriptYou) transcriptYou.textContent = `"${queryText}"`;

    try {
      const res = await fetch('/api/conversation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryText, language: currentLanguage })
      });
      const data = await res.json();

      if (data && data.speech) {
        if (intelLastInstruction) intelLastInstruction.textContent = `"${data.speech}"`;
        if (transcriptMark) transcriptMark.textContent = `"${data.speech}"`;

        if (data.action === "ENABLE_AI_MODE") setAiMode(true);
        else if (data.action === "DISABLE_AI_MODE") setAiMode(false);

        // Emergency & Telephony Handling (Direct Dial Execution)
        if (data.action === "EMERGENCY_CALL" || data.action === "CALL_FAMILY" || data.intent === "EMERGENCY" || data.intent === "FAMILY_CALL_REQUEST") {
          const rawPhone = data.target || "+1 949 738 5095";
          const cleanPhone = rawPhone.replace(/[^\d+]/g, '');
          if (emergencyActiveBanner) emergencyActiveBanner.style.display = 'flex';
          if (emergencyCallStatusText) {
            emergencyCallStatusText.textContent = `Calling family contact (${rawPhone}) • Caretaker Stream Synced`;
          }
          const dialBtn = document.getElementById('btn-emergency-dial');
          if (dialBtn) {
            dialBtn.href = `tel:${cleanPhone}`;
            dialBtn.textContent = `📞 Dial Call (${rawPhone})`;
          }
          try {
            window.location.href = `tel:${cleanPhone}`;
          } catch (e) {
            console.warn("[Dialer trigger]", e);
          }
        }

        playAudioAlert(data.speech, data.priority || 'NORMAL', true);
      } else {
        const fallbackMsg = currentLanguage.startsWith("te") ? "సర్, మీ మాట నాకు వినిపించలేదు. మరోసారి చెప్పండి." : "Sir, I couldn't hear clearly. Please speak again.";
        if (transcriptMark) transcriptMark.textContent = `"${fallbackMsg}"`;
        playAudioAlert(fallbackMsg, "NORMAL", true);
      }
    } catch (err) {
      console.error("[AGENT Error]", err);
      const errMsg = currentLanguage.startsWith("te") ? "సర్, కనెక్షన్ లో సమస్య ఉంది." : "Sir, connection error.";
      if (transcriptMark) transcriptMark.textContent = `"${errMsg}"`;
      playAudioAlert(errMsg, "NORMAL", true);
    }
  };

  // SOS Emergency Trigger Button Handler
  const btnTriggerSos = document.getElementById('btn-trigger-sos');
  if (btnTriggerSos) {
    btnTriggerSos.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/emergency/trigger', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: 'BUTTON' })
        });
        const data = await res.json();
        if (emergencyActiveBanner) emergencyActiveBanner.style.display = 'flex';
        const msg = currentLanguage.startsWith("te") ? "సర్, ఎమర్జెన్సీ కాల్ చేస్తున్నాను." : "Sir, initiating emergency call immediately.";
        if (transcriptMark) transcriptMark.textContent = `"${msg}"`;
        playAudioAlert(msg, "CRITICAL", true);
      } catch (err) {
        console.error(err);
      }
    });
  }

  // Resolve Emergency Button Handler
  if (btnResolveEmergency) {
    btnResolveEmergency.addEventListener('click', async () => {
      try {
        await fetch('/api/emergency/resolve', { method: 'POST' });
        if (emergencyActiveBanner) emergencyActiveBanner.style.display = 'none';
        const msg = currentLanguage.startsWith("te") ? "సర్, ఎమర్జెన్సీ క్లియర్ చేయబడింది." : "Sir, emergency resolved.";
        if (transcriptMark) transcriptMark.textContent = `"${msg}"`;
        playAudioAlert(msg, "NORMAL", true);
      } catch (err) {}
    });
  }

  // ── 2. AI MODE & LANGUAGE TOGGLE ──
  if (btnToggleAiMode) {
    btnToggleAiMode.addEventListener('click', () => setAiMode(!isAiMode));
  }

  function setAiMode(enabled) {
    isAiMode = enabled;
    fetch('/api/set_ai_mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: isAiMode })
    }).catch(() => {});

    if (btnToggleAiMode) {
      if (isAiMode) {
        btnToggleAiMode.textContent = '● AI: ACTIVE';
        btnToggleAiMode.style.background = 'rgba(16, 185, 129, 0.15)';
        btnToggleAiMode.style.borderColor = '#10b981';
        btnToggleAiMode.style.color = '#10b981';
      } else {
        btnToggleAiMode.textContent = '○ AI: PAUSED';
        btnToggleAiMode.style.background = 'rgba(113, 113, 122, 0.15)';
        btnToggleAiMode.style.borderColor = '#71717a';
        btnToggleAiMode.style.color = '#71717a';
      }
    }
  }

  if (btnToggleLang) {
    btnToggleLang.addEventListener('click', () => {
      if (currentLanguage === 'te-IN') {
        currentLanguage = 'en-US';
        btnToggleLang.textContent = '🌐 English (EN)';
        btnToggleLang.style.borderColor = '#10b981';
        btnToggleLang.style.color = '#10b981';
      } else {
        currentLanguage = 'te-IN';
        btnToggleLang.textContent = '🌐 తెలుగు (Telugu)';
        btnToggleLang.style.borderColor = '#38bdf8';
        btnToggleLang.style.color = '#38bdf8';
      }
      if (speechRecognizer) speechRecognizer.lang = currentLanguage;
    });
  }

  // ── 3. TAB NAVIGATION ──
  function switchTab(activeTab, showView) {
    [tabLive, tabGuardian, tabHistory].forEach(t => { if (t) t.classList.remove('active'); });
    [viewLive, viewGuardian, viewHistory].forEach(v => { if (v) v.style.display = 'none'; });
    
    activeTab.classList.add('active');
    showView.style.display = (showView === viewLive || showView === viewGuardian) ? 'grid' : 'flex';
  }

  if (tabLive) tabLive.addEventListener('click', () => switchTab(tabLive, viewLive));
  if (tabGuardian) tabGuardian.addEventListener('click', () => switchTab(tabGuardian, viewGuardian));
  if (tabHistory) tabHistory.addEventListener('click', async () => {
    switchTab(tabHistory, viewHistory);
    await loadHistory();
  });

  // ── 4. CAMERA & CONTROLLED INFERENCE STREAM ──
  const bufCanvas = document.createElement('canvas');
  bufCanvas.width = 640;
  bufCanvas.height = 360;
  const bufCtx = bufCanvas.getContext('2d');

  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280, min: 640 }, height: { ideal: 720, min: 360 }, facingMode: "environment" },
        audio: false
      });
      videoEl.srcObject = stream;
      await videoEl.play();

      isCameraActive = true;
      cameraOfflineMsg.style.display = 'none';
      btnToggleCamera.textContent = "■ Stop Camera";
      btnToggleCamera.style.borderColor = "#ef4444";
      btnToggleCamera.style.color = "#ef4444";

      if (hudCamStatus) {
        hudCamStatus.textContent = "● SENSOR ACTIVE";
        hudCamStatus.style.color = "#10b981";
      }

      fetch('/api/session/start', { method: 'POST' });

      // Controlled High-Speed Frame Dispatcher (12-14 FPS with adaptive backpressure)
      if (frameTimer) clearInterval(frameTimer);
      isFrameInFlight = false;

      videoEl.onloadedmetadata = () => {
        const vw = videoEl.videoWidth || 640;
        const vh = videoEl.videoHeight || 360;
        bufCanvas.width = 480;
        bufCanvas.height = Math.round(480 * (vh / vw));
        if (canvasEl) {
          canvasEl.width = 640;
          canvasEl.height = Math.round(640 * (vh / vw));
        }
      };

      frameTimer = setInterval(() => {
        if (!videoEl || videoEl.videoWidth === 0 || !isCameraActive) return;
        
        const now = Date.now();
        if (isFrameInFlight && (now - lastFrameSentTime < 80)) return;

        if (ws && ws.readyState === WebSocket.OPEN && ws.bufferedAmount === 0) {
          const bw = bufCanvas.width || 480;
          const bh = bufCanvas.height || 270;
          bufCtx.drawImage(videoEl, 0, 0, bw, bh);
          const dataUrl = bufCanvas.toDataURL('image/jpeg', 0.65);
          const b64 = dataUrl.split(',')[1];

          if (b64) {
            isFrameInFlight = true;
            lastFrameSentTime = now;
            ws.send(JSON.stringify({
              type: "frame",
              image: b64,
              ai_mode: isAiMode,
              language: currentLanguage,
              timestamp: now / 1000.0
            }));
          }
        }
      }, 70); // Smooth 12-14 FPS real-time rate
    } catch (err) {
      console.warn("[CAMERA Access Error]", err);
      handleCameraDisconnected();
    }
  }

  function stopCamera() {
    if (frameTimer) clearInterval(frameTimer);
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    isCameraActive = false;
    handleCameraDisconnected();
  }

  function handleCameraDisconnected() {
    cameraOfflineMsg.style.display = 'flex';
    btnToggleCamera.textContent = "▶ Start Camera";
    btnToggleCamera.style.borderColor = "#10b981";
    btnToggleCamera.style.color = "#10b981";

    if (hudCamStatus) {
      hudCamStatus.textContent = "○ SENSOR DISCONNECTED";
      hudCamStatus.style.color = "#71717a";
    }
    if (intelRiskLevel) {
      intelRiskLevel.textContent = "UNKNOWN (CAMERA DISCONNECTED)";
      intelRiskLevel.style.color = "#71717a";
    }
    if (intelPathStatus) {
      intelPathStatus.textContent = "AI SAFETY UNKNOWN";
      intelPathStatus.style.color = "#71717a";
    }
    if (intelDecisionPill) {
      intelDecisionPill.textContent = "STATUS: ⚠️ SENSOR OFFLINE";
      intelDecisionPill.style.color = "#f59e0b";
    }
    if (intelLastInstruction) {
      intelLastInstruction.textContent = '"సర్, కెమెరా నుంచి సమాచారం సరిగ్గా రావడం లేదు. ఒకసారి ఆగండి."';
    }
    if (intelligenceCard) {
      intelligenceCard.className = "app-intelligence-card UNKNOWN";
    }
    if (trackingList) {
      trackingList.innerHTML = `<div style="color: #71717a; text-align: center; padding: 6px;">Camera disconnected — no visual data</div>`;
    }
    if (envTotalTag) envTotalTag.textContent = "0 OBJECTS";

    if (ctx) ctx.clearRect(0, 0, 640, 360);
  }

  if (btnToggleCamera) {
    btnToggleCamera.addEventListener('click', () => {
      if (isCameraActive) stopCamera();
      else startCamera();
    });
  }

  // ── 5. WEBSOCKET SUBSCRIPTION ──
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host || 'localhost:5000'}/ws/stream`;
    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      isFrameInFlight = false; // Release backpressure gate immediately
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "detection_update") {
          updateWorkspace(payload);
        }
      } catch (err) {}
    };

    ws.onclose = () => {
      isFrameInFlight = false;
      setTimeout(connectWebSocket, 2000);
    };
  }

  // ── 6. INCREMENTAL DOM & CANVAS RENDERING (Zero Layout Thrashing) ──
  function updateWorkspace(payload) {
    if (!isCameraActive) return;

    const objects = payload.objects || [];
    const highestThreat = payload.highest_threat || "SILENT";
    const markMsg = payload.mark_message || "";
    const voiceOutput = payload.voice_output || {};
    const stats = payload.stats || {};
    const emergencyState = payload.emergency || {};

    // 0. Synchronize Emergency Banner
    if (emergencyState.is_active && emergencyActiveBanner) {
      emergencyActiveBanner.style.display = 'flex';
      if (emergencyCallStatusText) {
        const phone = emergencyState.contact_phone || "+1 949 738 5095";
        emergencyCallStatusText.textContent = `Calling family contact (${phone}) • Caretaker Stream Synced`;
      }
    } else if (!emergencyState.is_active && emergencyActiveBanner) {
      emergencyActiveBanner.style.display = 'none';
    }

    drawBoundingBoxes(objects);

    if (!isAiMode) {
      if (cachedRiskClass !== "PAUSED") {
        cachedRiskClass = "PAUSED";
        intelRiskLevel.textContent = "AI MONITORING PAUSED";
        intelRiskLevel.style.color = "#71717a";
        intelPathStatus.textContent = "CONVERSATION STANDBY";
        intelPathStatus.style.color = "#38bdf8";
        intelDecisionPill.textContent = "STATUS: ⏸️ AI PAUSED (MIC ACTIVE)";
        intelligenceCard.className = "app-intelligence-card UNKNOWN";
      }
    } else if (highestThreat !== cachedThreat) {
      cachedThreat = highestThreat;

      if (highestThreat === "RED" || highestThreat === "URGENT" || highestThreat === "CRITICAL") {
        intelRiskLevel.textContent = "CRITICAL / URGENT";
        intelRiskLevel.style.color = "#ef4444";
        intelPathStatus.textContent = "HAZARD IN CORRIDOR";
        intelPathStatus.style.color = "#ef4444";
        intelDecisionPill.textContent = "DECISION: 🚨 IMMEDIATE STOP";
        intelligenceCard.className = "app-intelligence-card RED";
      } else if (highestThreat === "YELLOW" || highestThreat === "CAUTION") {
        intelRiskLevel.textContent = "MEDIUM (CAUTION)";
        intelRiskLevel.style.color = "#f59e0b";
        intelPathStatus.textContent = "OBSTACLE NEARBY";
        intelPathStatus.style.color = "#f59e0b";
        intelDecisionPill.textContent = "DECISION: ⚠️ CAUTION";
        intelligenceCard.className = "app-intelligence-card YELLOW";
      } else if (objects.length > 0) {
        intelRiskLevel.textContent = "LOW (AWARENESS)";
        intelRiskLevel.style.color = "#38bdf8";
        intelPathStatus.textContent = "MONITORING SCENE";
        intelPathStatus.style.color = "#38bdf8";
        intelDecisionPill.textContent = "DECISION: 🤫 SILENT MONITORING";
        intelligenceCard.className = "app-intelligence-card GREEN";
      } else {
        intelRiskLevel.textContent = "LOW (SAFE)";
        intelRiskLevel.style.color = "#10b981";
        intelPathStatus.textContent = "PATH CLEAR";
        intelPathStatus.style.color = "#10b981";
        intelDecisionPill.textContent = "DECISION: 🤫 CLEAR SILENCE";
        intelligenceCard.className = "app-intelligence-card GREEN";
      }
    }

    if (markMsg && markMsg !== "Path clear." && markMsg !== "AI MODE PAUSED") {
      intelLastInstruction.textContent = `"${markMsg}"`;
    }

    const newKey = objects.map(o => `${o.track_id || o.id}:${o.motion_state}:${o.distance_m}`).join('|');
    if (newKey !== cachedObjectsKey) {
      cachedObjectsKey = newKey;
      envTotalTag.textContent = `${objects.length} OBJECT${objects.length === 1 ? '' : 'S'}`;

      if (objects.length === 0) {
        trackingList.innerHTML = `<div style="color: #71717a; text-align: center; padding: 6px;">Corridor clear — zero obstacles</div>`;
      } else {
        let trackHtml = '';
        objects.forEach((obj, idx) => {
          const name = (obj.recognized_name || obj.class_name || obj.name || 'Object').toUpperCase();
          const threat = (obj.risk_level || obj.threat || 'LOW').toUpperCase();
          const trackId = obj.track_id || obj.id || (idx + 1);
          const conf = obj.confidence ? Math.round(obj.confidence * 100) : 85;
          const distStr = (obj.distance_info && obj.distance_info.distance_m) ? `${obj.distance_info.distance_m}m` : (obj.proximity || '2.0m');
          const motionStr = obj.motion_state || (obj.motion ? obj.motion.state : 'STATIONARY');

          let dotColor = '#10b981';
          if (threat === 'RED' || threat === 'URGENT') dotColor = '#ef4444';
          else if (threat === 'YELLOW' || threat === 'CAUTION') dotColor = '#f59e0b';
          else if (threat === 'AWARENESS') dotColor = '#38bdf8';

          trackHtml += `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 2px 4px; border-bottom: 1px solid rgba(255,255,255,0.04);">
              <span style="color:#fff;">#0${trackId} ${name} (${conf}%) • ${distStr}</span>
              <span style="color:${dotColor}; font-weight:700;">${motionStr}</span>
            </div>
          `;
        });
        trackingList.innerHTML = trackHtml;
      }
    }

    if (stats.fps !== undefined && hudLatency) {
      hudLatency.textContent = `FPS: ${stats.fps} • ~${stats.latency_ms || 10}ms`;
    }

    if (isAiMode && voiceOutput.should_speak && voiceOutput.spoken_message) {
      if (micState === 'IDLE' || voiceOutput.priority === 'CRITICAL' || voiceOutput.interrupt_audio) {
        if (transcriptMark) transcriptMark.textContent = `"${voiceOutput.spoken_message}"`;
        playAudioAlert(voiceOutput.spoken_message, voiceOutput.priority || 'NORMAL', voiceOutput.interrupt_audio);
      }
    }
  }

  function drawBoundingBoxes(objects) {
    if (!ctx || !canvasEl) return;
    const w = canvasEl.width || 640;
    const h = canvasEl.height || 360;
    ctx.clearRect(0, 0, w, h);

    objects.forEach((obj, idx) => {
      const [nx1, ny1, nx2, ny2] = obj.norm_bbox || [0, 0, 0, 0];
      const x1 = nx1 * w;
      const y1 = ny1 * h;
      const bw = Math.max(10, (nx2 - nx1) * w);
      const bh = Math.max(10, (ny2 - ny1) * h);

      const name = (obj.recognized_name || obj.class_name || obj.name || 'Object').toUpperCase();
      const threat = (obj.risk_level || obj.threat || 'LOW').toUpperCase();
      const trackId = obj.track_id || obj.id || (idx + 1);
      const conf = obj.confidence ? Math.round(obj.confidence * 100) : 85;

      let color = "#10b981";
      if (threat === "RED" || threat === "URGENT") color = "#ef4444";
      else if (threat === "YELLOW" || threat === "CAUTION") color = "#f59e0b";
      else if (threat === "AWARENESS") color = "#38bdf8";

      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      ctx.strokeRect(x1, y1, bw, bh);

      const distStr = (obj.distance_info && obj.distance_info.distance_m) ? `${obj.distance_info.distance_m}m` : (obj.proximity || '2.0m');
      const motionStr = obj.motion_state || (obj.motion ? obj.motion.state : 'STATIONARY');
      const label = `#0${trackId} ${name} (${conf}%) • ${distStr} • ${motionStr}`;
      ctx.font = "bold 11px 'JetBrains Mono', monospace";
      const tw = ctx.measureText(label).width;

      ctx.fillStyle = "rgba(0,0,0,0.85)";
      ctx.fillRect(x1, Math.max(0, y1 - 20), tw + 10, 18);

      ctx.fillStyle = color;
      ctx.fillText(label, x1 + 4, Math.max(12, y1 - 6));
    });
  }

  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      const sessions = data.sessions || [];
      let html = '';
      sessions.forEach(s => {
        html += `
          <div style="background:#18181c; border:1px solid #27272a; padding:10px 14px; border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div style="font-weight:700; color:#fff;">${s.date_label || 'Recent Session'}</div>
              <div style="color:#a1a1aa; font-size:11px; margin-top:2px;">Duration: ${s.duration_min || 10} min • [ ${s.total_detections || 45} Detections ] [ ${s.total_alerts || 6} Spoken Alerts ]</div>
            </div>
            <span style="background:rgba(16,185,129,0.15); color:#10b981; padding:3px 8px; border-radius:4px; font-weight:800; font-size:10px;">COMPLETED</span>
          </div>
        `;
      });
      historyContainer.innerHTML = html;
    } catch (e) {}
  }

  // Auto-Connect on Mount
  connectWebSocket();
  setupSpeechRecognizer();
  startCamera();
});
