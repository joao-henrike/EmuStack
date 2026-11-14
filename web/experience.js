/* EmuStack Phase 2: browser-only TV, display and gamepad preferences. */
(function attachExperience(root) {
  'use strict';
  const STORAGE_KEY = 'emustack:experience:v1';
  const DEFAULTS = Object.freeze({tv:false, gamepad:true, contrast:false, reduceMotion:false});

  function normalizePreferences(value) {
    const source = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    const result = {};
    for (const key of Object.keys(DEFAULTS)) {
      result[key] = typeof source[key] === 'boolean' ? source[key] : DEFAULTS[key];
    }
    return result;
  }

  function parsePreferences(raw) {
    try { return normalizePreferences(JSON.parse(raw)); }
    catch (_) { return normalizePreferences(null); }
  }

  function nextFocusIndex(total, current, step) {
    if (!Number.isInteger(total) || total <= 0) return -1;
    if (current < 0 || current >= total) return step < 0 ? total - 1 : 0;
    return (current + (step < 0 ? -1 : 1) + total) % total;
  }

  function gamepadIntent(pad) {
    if (!pad || !pad.connected) return null;
    const pressed = index => Boolean(pad.buttons && pad.buttons[index] && pad.buttons[index].pressed);
    if (pressed(0)) return 'activate'; // A / Cross
    if (pressed(1)) return 'back';     // B / Circle
    if (pressed(9)) return 'settings'; // Start / Options
    if (pressed(12) || pressed(14) || (pad.axes && (pad.axes[1] < -0.7 || pad.axes[0] < -0.7))) return 'previous';
    if (pressed(13) || pressed(15) || (pad.axes && (pad.axes[1] > 0.7 || pad.axes[0] > 0.7))) return 'next';
    return null;
  }

  function init(options) {
    const document = root.document;
    if (!document) return null;
    const byId = id => document.getElementById(id);
    const dialog = byId('experience-dialog');
    const toggle = byId('tv-mode-toggle');
    const settings = byId('experience-settings');
    if (!dialog || !toggle || !settings) return null;
    let prefs;
    try { prefs = parsePreferences(root.localStorage.getItem(STORAGE_KEY)); }
    catch (_) { prefs = normalizePreferences(null); }
    let frame = 0;
    let lastIntent = null;
    let controllerOnline = null;

    function visibleTargets() {
      const modal = document.querySelector('dialog[open]');
      const scope = modal || document;
      const query = modal ? 'button, a[href], input, select, [tabindex="0"]'
        : '.sidebar .nav-item, .topbar button, .view.active button, .view.active a[href], .view.active input, .view.active select';
      return [...scope.querySelectorAll(query)].filter(el =>
        !el.disabled && el.getClientRects().length > 0 && el.getAttribute('aria-hidden') !== 'true'
      );
    }

    function moveFocus(direction) {
      const targets = visibleTargets();
      const index = nextFocusIndex(targets.length, targets.indexOf(document.activeElement), direction);
      if (index !== -1) targets[index].focus();
    }

    function updateControllerStatus(online) {
      if (online === controllerOnline) return;
      controllerOnline = online;
      const status = byId('experience-gamepad-status');
      if (status) {
        status.textContent = !root.navigator || typeof root.navigator.getGamepads !== 'function'
          ? 'Gamepad API indisponível neste navegador.'
          : online ? 'Controle detectado. D-pad: navegar; A: selecionar; B: voltar; Start: ajustes.'
                   : 'Nenhum controle conectado. Use as setas e Enter como alternativa.';
      }
    }

    function handleIntent(intent) {
      if (intent === 'previous') moveFocus(-1);
      if (intent === 'next') moveFocus(1);
      if (intent === 'activate') {
        const targets = visibleTargets();
        const target = document.activeElement;
        if (targets.includes(target)) target.click();
        else moveFocus(1);
      }
      if (intent === 'back') {
        const modal = document.querySelector('dialog[open]');
        if (modal) modal.close();
        else if (options && typeof options.onBack === 'function') options.onBack();
      }
      if (intent === 'settings' && !dialog.open) dialog.showModal();
    }

    function stopPolling() {
      if (frame && typeof root.cancelAnimationFrame === 'function') root.cancelAnimationFrame(frame);
      frame = 0;
      lastIntent = null;
    }

    function poll() {
      frame = 0;
      if (!prefs.tv || !prefs.gamepad || document.visibilityState === 'hidden') return;
      let connected = false;
      let intent = null;
      try {
        const pads = root.navigator && typeof root.navigator.getGamepads === 'function'
          ? root.navigator.getGamepads() : [];
        const pad = [...(pads || [])].find(p => p && p.connected);
        connected = Boolean(pad);
        intent = gamepadIntent(pad);
      } catch (_) { /* Browser device restrictions never break the dashboard. */ }
      updateControllerStatus(connected);
      if (intent && intent !== lastIntent) handleIntent(intent);
      lastIntent = intent;
      if (typeof root.requestAnimationFrame === 'function') frame = root.requestAnimationFrame(poll);
    }

    function startPolling() {
      stopPolling();
      if (prefs.tv && prefs.gamepad && document.visibilityState !== 'hidden' &&
          typeof root.requestAnimationFrame === 'function') frame = root.requestAnimationFrame(poll);
    }

    function apply() {
      document.body.classList.toggle('tv-mode', prefs.tv);
      document.body.classList.toggle('experience-contrast', prefs.contrast);
      document.body.classList.toggle('experience-reduced-motion', prefs.reduceMotion);
      toggle.setAttribute('aria-pressed', String(prefs.tv));
      toggle.textContent = prefs.tv ? 'Sair do modo TV' : 'Modo TV';
      for (const [key, id] of [
        ['tv', 'experience-tv'], ['gamepad', 'experience-gamepad'],
        ['contrast', 'experience-contrast'], ['reduceMotion', 'experience-motion']
      ]) {
        const input = byId(id);
        if (input) input.checked = prefs[key];
      }
      startPolling();
    }

    function update(name, value) {
      if (!Object.prototype.hasOwnProperty.call(DEFAULTS, name)) return;
      prefs = normalizePreferences({ ...prefs, [name]: Boolean(value) });
      try { root.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs)); } catch (_) { /* optional */ }
      apply();
    }

    function syncFullscreen() {
      const button = byId('experience-fullscreen');
      if (!button) return;
      button.textContent = document.fullscreenElement ? 'Sair da tela cheia' : 'Entrar em tela cheia';
      button.setAttribute('aria-pressed', String(Boolean(document.fullscreenElement)));
    }

    toggle.addEventListener('click', () => update('tv', !prefs.tv));
    settings.addEventListener('click', () => dialog.showModal());
    byId('close-experience').addEventListener('click', () => dialog.close());
    for (const [key, id] of [
      ['tv', 'experience-tv'], ['gamepad', 'experience-gamepad'],
      ['contrast', 'experience-contrast'], ['reduceMotion', 'experience-motion']
    ]) byId(id).addEventListener('change', event => update(key, event.target.checked));
    byId('experience-fullscreen').addEventListener('click', async () => {
      try {
        if (document.fullscreenElement) await document.exitFullscreen();
        else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
        else throw new Error('API de tela cheia indisponível');
      } catch (_) {
        const status = byId('experience-fullscreen-status');
        if (status) status.textContent = 'O navegador não permitiu tela cheia. Use o comando do navegador.';
      }
      syncFullscreen();
    });
    document.addEventListener('fullscreenchange', syncFullscreen);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') stopPolling();
      else startPolling();
    });
    document.addEventListener('keydown', event => {
      if (!prefs.tv || event.defaultPrevented || event.ctrlKey || event.altKey || event.metaKey) return;
      const active = document.activeElement;
      if (active && (['INPUT','TEXTAREA','SELECT'].includes(active.tagName) || active.isContentEditable)) return;
      if (['ArrowUp','ArrowLeft','ArrowDown','ArrowRight'].includes(event.key)) {
        event.preventDefault();
        moveFocus(['ArrowUp','ArrowLeft'].includes(event.key) ? -1 : 1);
      }
    });
    root.addEventListener('gamepadconnected', () => updateControllerStatus(true));
    root.addEventListener('gamepaddisconnected', () => updateControllerStatus(false));
    syncFullscreen();
    updateControllerStatus(false);
    apply();
    return Object.freeze({ getPreferences: () => ({ ...prefs }) });
  }

  const api = Object.freeze({ normalizePreferences, parsePreferences, nextFocusIndex, gamepadIntent, init });
  root.EmuStackExperience = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
