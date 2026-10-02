/* -------------------------------------------------------------
 * S.A.R.A — Smart Assistant for Responsive Actions
 * Frontend client: Web Speech API (primary) + Gemini STT fallback,
 * SSE streaming chat, ElevenLabs TTS playback, visualizer, device actions.
 * ------------------------------------------------------------- */

(() => {
  'use strict';

  // ---------- DOM ----------
  const $ = (id) => document.getElementById(id);
  const boot = $('boot');
  const bootFill = $('boot-fill');
  const bootStatus = $('boot-status');
  const hud = $('hud');
  const chatEl = $('chat');
  const textInput = $('text-input');
  const micBtn = $('mic-btn');
  const sendBtn = $('send-btn');
  const clearBtn = $('clear-btn');
  const sysTime = $('sys-time');
  const sysStatus = $('sys-status');
  const sysBattery = $('sys-battery');
  const connDot = $('conn-dot');
  const brandSub = $('brand-sub');
  const core = document.querySelector('.core');
  const voiceWave = $('voice-wave');
  const listenHint = $('listen-hint');
  const ttsAudio = $('tts-audio');
  const wakeAudio = $('wake-audio');
  const toolFeed = $('tool-feed');
  const vizCanvas = $('viz');
  const starCanvas = $('starfield');

  // ---------- State ----------
  const state = {
    history: [],       // {role, text}
    listening: false,
    speaking: false,
    processing: false,
    awake: false,
    wakeWordEnabled: false,
    timers: [],
  };

  // ---------- Boot sequence ----------
  async function bootSequence() {
    const steps = [
      [10, 'Initializing core systems…'],
      [25, 'Establishing neural link…'],
      [45, 'Loading Gemini cognition module…'],
      [65, 'Calibrating ElevenLabs vocal matrix…'],
      [85, 'Running diagnostics…'],
      [100, 'Systems online.'],
    ];
    for (const [pct, msg] of steps) {
      bootFill.style.width = pct + '%';
      bootStatus.textContent = msg;
      await sleep(380);
    }

    try {
      const cfg = await fetch('/api/config').then(r => r.json());
      state.config = cfg;
      document.title = `${cfg.name} — ${cfg.full_name}`;
    } catch (e) { console.warn(e); }

    // Fetch wake greeting
    try {
      const w = await fetch('/api/wake').then(r => r.json());
      if (w.audio_base64) {
        wakeAudio.src = w.audio_base64;
        appendMsg('assistant', w.text, true);
        try { await wakeAudio.play(); } catch (_) { /* autoplay block */ }
      }
    } catch (e) { console.warn(e); }

    boot.classList.add('hidden-boot');
    setTimeout(() => { boot.style.display = 'none'; hud.classList.remove('hidden'); }, 800);
    state.awake = true;
    setInterval(tickClock, 1000); tickClock();
    initBattery();
    initStarfield();
    initVisualizer();
    initSpeechRecognition();
    initKeyboardWake();
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  // ---------- Clock & battery ----------
  function tickClock() {
    const d = new Date();
    sysTime.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  async function initBattery() {
    try {
      if (navigator.getBattery) {
        const b = await navigator.getBattery();
        const update = () => {
          sysBattery.textContent = Math.round(b.level * 100) + '%' + (b.charging ? ' ⚡' : '');
          sysBattery.className = 'sys-val ' + (b.level < 0.2 ? 'err' : b.charging ? 'ok' : '');
        };
        update();
        b.addEventListener('levelchange', update);
        b.addEventListener('chargingchange', update);
      } else {
        sysBattery.textContent = 'N/A';
      }
    } catch (_) { sysBattery.textContent = 'N/A'; }
  }

  // ---------- Starfield background ----------
  function initStarfield() {
    const ctx = starCanvas.getContext('2d');
    let w, h, stars;
    function resize() {
      w = starCanvas.width = window.innerWidth;
      h = starCanvas.height = window.innerHeight;
      stars = Array.from({ length: 90 }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        z: Math.random() * 0.8 + 0.2,
        s: Math.random() * 1.2 + 0.3,
      }));
    }
    resize(); window.addEventListener('resize', resize);
    function frame() {
      ctx.clearRect(0, 0, w, h);
      for (const s of stars) {
        ctx.fillStyle = `rgba(0, 212, 255, ${0.2 + s.z * 0.5})`;
        ctx.beginPath(); ctx.arc(s.x, s.y, s.s, 0, Math.PI * 2); ctx.fill();
        s.y += 0.15 * s.z;
        if (s.y > h) { s.y = 0; s.x = Math.random() * w; }
      }
      requestAnimationFrame(frame);
    }
    frame();
  }

  // ---------- Visualizer (circular audio bars) ----------
  let audioCtx, analyser, micStream, vizAnimId;
  function initVisualizer() {
    const ctx = vizCanvas.getContext('2d');
    let w = 400, h = 400;
    function resize() {
      const rect = vizCanvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      vizCanvas.width = rect.width * dpr;
      vizCanvas.height = rect.height * dpr;
      w = vizCanvas.width; h = vizCanvas.height;
    }
    resize(); window.addEventListener('resize', resize);

    function draw() {
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2, cy = h / 2;
      const baseR = Math.min(w, h) * 0.32;
      const bars = 72;

      let levels = new Array(bars).fill(0.05);
      if (analyser && (state.listening || state.speaking)) {
        const buf = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(buf);
        const step = Math.floor(buf.length / bars);
        for (let i = 0; i < bars; i++) {
          let sum = 0;
          for (let j = 0; j < step; j++) sum += buf[i * step + j];
          levels[i] = sum / step / 255;
        }
      } else if (state.processing) {
        const t = Date.now() / 200;
        for (let i = 0; i < bars; i++) {
          levels[i] = 0.2 + 0.3 * Math.abs(Math.sin(t + i * 0.2));
        }
      } else {
        // idle gentle pulse
        const t = Date.now() / 800;
        for (let i = 0; i < bars; i++) {
          levels[i] = 0.04 + 0.08 * Math.abs(Math.sin(t + i * 0.18));
        }
      }

      ctx.save();
      ctx.translate(cx, cy);
      ctx.lineCap = 'round';
      for (let i = 0; i < bars; i++) {
        const ang = (i / bars) * Math.PI * 2 - Math.PI / 2;
        const len = 6 + levels[i] * 40;
        const x1 = Math.cos(ang) * baseR;
        const y1 = Math.sin(ang) * baseR;
        const x2 = Math.cos(ang) * (baseR + len);
        const y2 = Math.sin(ang) * (baseR + len);
        const alpha = 0.35 + levels[i] * 0.65;
        const color = state.listening
          ? `rgba(255,59,92,${alpha})`
          : state.speaking
            ? `rgba(0,255,157,${alpha})`
            : `rgba(0,212,255,${alpha})`;
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.shadowBlur = 8; ctx.shadowColor = color;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      }
      ctx.restore();
      vizAnimId = requestAnimationFrame(draw);
    }
    draw();
  }

  async function ensureAudioAnalyser() {
    if (audioCtx) return;
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    // We'll attach source when we get a mic stream OR when TTS plays.
  }

  async function attachMicAnalyser(stream) {
    await ensureAudioAnalyser();
    const src = audioCtx.createMediaStreamSource(stream);
    src.connect(analyser);
  }
  function attachTTSAnalyser() {
    if (!audioCtx) return;
    try {
      const src = audioCtx.createMediaElementSource(ttsAudio);
      src.connect(analyser);
      analyser.connect(audioCtx.destination);
    } catch (_) { /* already connected */ }
  }

  // ---------- Chat / SSE ----------
  function appendMsg(role, text, silent = false) {
    const d = document.createElement('div');
    d.className = 'msg ' + role;
    const speaker = document.createElement('span');
    speaker.className = 'speaker';
    speaker.textContent = role === 'user' ? 'YOU' : role === 'assistant' ? 'S.A.R.A' : 'SYSTEM';
    const body = document.createElement('span');
    body.textContent = text;
    d.appendChild(speaker);
    d.appendChild(body);
    chatEl.appendChild(d);
    chatEl.scrollTop = chatEl.scrollHeight;
    if (role !== 'system') state.history.push({ role, text });
    if (state.history.length > 40) state.history.splice(0, state.history.length - 40);
    return body;
  }

  function appendToolLine(name, result) {
    const d = document.createElement('div');
    d.className = 'tool-line';
    let label = 'Running';
    const action = result && result.action;
    if (action === 'open_url') label = `Opening ${result.url}`;
    else if (action === 'set_timer') label = `Timer set for ${result.seconds}s — ${result.label}`;
    else label = `Executing ${name.replace(/_/g, ' ')}`;
    d.innerHTML = `▸ <span class="tool-name">${label}</span>`;
    toolFeed.appendChild(d);
    toolFeed.scrollTop = toolFeed.scrollHeight;
    while (toolFeed.children.length > 8) toolFeed.removeChild(toolFeed.firstChild);
  }

  async function sendMessage(text) {
    if (!text || !text.trim()) return;
    if (state.processing) return;
    text = text.trim();
    appendMsg('user', text);
    textInput.value = '';
    setProcessing(true);

    const assistantBody = appendMsg('assistant', '', true);
    let fullAssistantText = '';

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: state.history.slice(0, -1) }),
      });
      if (!resp.ok || !resp.body) {
        assistantBody.textContent = 'I\'m having trouble reaching my core, ' + (state.config?.owner || 'Sir') + '.';
        setProcessing(false);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let audioBase64 = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop();
        for (const rawEvt of events) {
          const lines = rawEvt.split('\n');
          let evtName = null, evtData = null;
          for (const line of lines) {
            if (line.startsWith('event: ')) evtName = line.slice(7).trim();
            else if (line.startsWith('data: ')) {
              try { evtData = JSON.parse(line.slice(6)); } catch (_) {}
            }
          }
          if (!evtName || !evtData) continue;
          if (evtName === 'text') {
            fullAssistantText += evtData.text;
            assistantBody.textContent = fullAssistantText;
            chatEl.scrollTop = chatEl.scrollHeight;
          } else if (evtName === 'tool_call') {
            appendToolLine(evtData.name, null);
          } else if (evtName === 'tool_result') {
            appendToolLine(evtData.name, evtData.result);
            handleClientAction(evtData.name, evtData.result);
          } else if (evtName === 'end') {
            audioBase64 = evtData.audio_base64;
            if (evtData.text && !fullAssistantText) {
              fullAssistantText = evtData.text;
              assistantBody.textContent = fullAssistantText;
            }
            state.history[state.history.length - 1] = { role: 'assistant', text: fullAssistantText };
          }
        }
      }

      if (audioBase64) {
        await speakBase64(audioBase64);
      }
    } catch (err) {
      assistantBody.textContent = 'Connection issue: ' + err.message;
      connDot.classList.add('off');
    } finally {
      setProcessing(false);
    }
  }

  function handleClientAction(name, result) {
    if (!result || !result.action) return;
    if (result.action === 'open_url') {
      window.open(result.url, '_blank', 'noopener');
    } else if (result.action === 'set_timer') {
      createTimer(result.seconds, result.label);
    }
  }

  function createTimer(seconds, label) {
    const end = Date.now() + seconds * 1000;
    const id = setInterval(() => {
      const remain = Math.max(0, end - Date.now());
      brandSub.textContent = `Timer: ${Math.ceil(remain/1000)}s — ${label}`;
      if (remain <= 0) {
        clearInterval(id);
        brandSub.textContent = 'Standing by';
        // Chime
        try {
          const ac = new (window.AudioContext || window.webkitAudioContext)();
          const o = ac.createOscillator(); const g = ac.createGain();
          o.connect(g); g.connect(ac.destination); o.frequency.value = 880;
          g.gain.setValueAtTime(0.2, ac.currentTime);
          g.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + 0.6);
          o.start(); o.stop(ac.currentTime + 0.6);
          setTimeout(() => {
            const o2 = ac.createOscillator(); const g2 = ac.createGain();
            o2.connect(g2); g2.connect(ac.destination); o2.frequency.value = 1180;
            g2.gain.setValueAtTime(0.2, ac.currentTime);
            g2.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + 0.8);
            o2.start(); o2.stop(ac.currentTime + 0.8);
          }, 700);
        } catch(_) {}
        appendMsg('system', `Timer "${label}" complete`);
      }
    }, 200);
    state.timers.push(id);
  }

  async function speakBase64(b64) {
    state.speaking = true;
    updateCoreState();
    attachTTSAnalyser();
    ttsAudio.src = b64;
    try { await ttsAudio.play(); } catch (_) {}
    return new Promise((res) => {
      ttsAudio.onended = () => { state.speaking = false; updateCoreState(); res(); };
      ttsAudio.onerror = () => { state.speaking = false; updateCoreState(); res(); };
    });
  }

  function setProcessing(p) {
    state.processing = p;
    micBtn.classList.toggle('processing', p && !state.listening);
    updateCoreState();
    brandSub.textContent = p ? 'Processing request…' : (state.listening ? 'Listening…' : 'Standing by');
    connDot.classList.remove('off');
  }
  function updateCoreState() {
    core.classList.toggle('listening', state.listening);
    core.classList.toggle('speaking', state.speaking);
    core.classList.toggle('processing', state.processing && !state.listening && !state.speaking);
    voiceWave.classList.toggle('active', state.listening || state.speaking);
  }

  // ---------- Speech recognition ----------
  let recognition = null;
  let useWebSpeech = false;
  let mediaRecorder = null;
  let recordedChunks = [];
  let recognitionFinalText = '';

  function initSpeechRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      recognition = new SR();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      useWebSpeech = true;

      recognition.onstart = () => {
        state.listening = true; updateCoreState();
        listenHint.textContent = 'Listening…';
        brandSub.textContent = 'Listening…';
        micBtn.classList.add('listening');
        recognitionFinalText = '';
      };
      recognition.onresult = (ev) => {
        let interim = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const res = ev.results[i];
          if (res.isFinal) recognitionFinalText += res[0].transcript;
          else interim += res[0].transcript;
        }
        textInput.value = recognitionFinalText + interim;
      };
      recognition.onerror = (ev) => {
        console.warn('SR error', ev.error);
        stopListening();
        if (ev.error === 'not-allowed') {
          appendMsg('system', 'Microphone access denied. You can still type.');
        }
      };
      recognition.onend = () => {
        const text = (recognitionFinalText || textInput.value || '').trim();
        stopListening();
        if (text) {
          textInput.value = '';
          sendMessage(text);
        } else {
          listenHint.textContent = 'Tap the microphone or type a command';
        }
      };
    } else {
      // Fallback: use MediaRecorder + Gemini STT endpoint
      useWebSpeech = false;
    }
  }

  async function startListening() {
    if (state.listening || state.processing) return;
    if (ttsAudio && !ttsAudio.paused) ttsAudio.pause();
    textInput.value = '';
    if (useWebSpeech && recognition) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        attachMicAnalyser(stream);
        // Keep the stream alive through recognition
        state._micStream = stream;
        recognition.start();
      } catch (err) {
        appendMsg('system', 'Microphone unavailable: ' + err.message);
      }
    } else {
      // Fallback: record audio, send to /api/stt
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
        attachMicAnalyser(stream);
        state._micStream = stream;
        recordedChunks = [];
        const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
        mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
        mediaRecorder.ondataavailable = (e) => { if (e.data.size) recordedChunks.push(e.data); };
        mediaRecorder.onstop = async () => {
          const blob = new Blob(recordedChunks, { type: 'audio/webm' });
          const reader = new FileReader();
          reader.onloadend = async () => {
            setProcessing(true);
            try {
              const r = await fetch('/api/stt', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ audio_data_url: reader.result }),
              }).then(x => x.json());
              const text = (r.text || '').trim();
              if (text) sendMessage(text);
              else { setProcessing(false); appendMsg('system', 'Did not catch that.'); }
            } catch (err) { setProcessing(false); appendMsg('system', 'STT error: ' + err.message); }
            cleanupStream();
          };
          reader.readAsDataURL(blob);
        };
        state.listening = true; updateCoreState();
        listenHint.textContent = 'Listening… (tap mic when done)';
        brandSub.textContent = 'Listening…';
        micBtn.classList.add('listening');
        mediaRecorder.start();
      } catch (err) {
        appendMsg('system', 'Microphone unavailable: ' + err.message);
      }
    }
  }

  function stopListening() {
    state.listening = false; updateCoreState();
    micBtn.classList.remove('listening');
    listenHint.textContent = 'Tap the microphone or type a command';
    if (useWebSpeech && recognition) {
      try { recognition.stop(); } catch (_) {}
    } else if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    } else {
      cleanupStream();
    }
  }

  function cleanupStream() {
    if (state._micStream) {
      state._micStream.getTracks().forEach(t => t.stop());
      state._micStream = null;
    }
  }

  // Keyboard wake: press Ctrl/Cmd+Space to start listening
  function initKeyboardWake() {
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.code === 'Space') {
        e.preventDefault();
        if (state.listening) stopListening(); else startListening();
      }
    });
  }

  // ---------- UI events ----------
  sendBtn.addEventListener('click', () => sendMessage(textInput.value));
  textInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMessage(textInput.value); });
  micBtn.addEventListener('click', () => { if (state.listening) stopListening(); else startListening(); });
  clearBtn.addEventListener('click', () => {
    state.history = [];
    chatEl.innerHTML = '';
    toolFeed.innerHTML = '';
    appendMsg('system', 'Memory cleared');
  });

  // Hold-to-talk on mobile (touchstart/touchend) as well as click fallback above.
  ['touchstart', 'mousedown'].forEach(evt => {
    micBtn.addEventListener(evt, (e) => {
      if (evt === 'mousedown' && e.button !== 0) return;
      if (!state.listening && !state.processing) startListening();
    });
  });
  ['touchend', 'mouseup', 'mouseleave'].forEach(evt => {
    micBtn.addEventListener(evt, () => {
      if (state.listening && !useWebSpeech) {
        // For MediaRecorder fallback, tap-to-toggle is easier, so only stop on second tap (handled by click).
      }
    });
  });

  // Pause TTS when user starts typing/clicking mic
  textInput.addEventListener('focus', () => { if (ttsAudio && !ttsAudio.paused) ttsAudio.pause(); });

  // Connection watchdog
  setInterval(async () => {
    try {
      const r = await fetch('/api/health', { cache: 'no-store' });
      if (r.ok) connDot.classList.remove('off'); else connDot.classList.add('off');
    } catch { connDot.classList.add('off'); }
  }, 15000);

  // ---------- Start ----------
  window.addEventListener('load', bootSequence);
})();
