/* Pure launch recommendations shared by the dashboard and Node regression tests. */
(function attachEmuStackLaunch(root) {
  'use strict';

  function recommendEmulatorForGame(gamePath = '') {
    const path = String(gamePath).toLowerCase();
    const ext = path.includes('.') ? path.slice(path.lastIndexOf('.')) : '';
    const normalized = path.replaceAll('\\', '/');
    const rules = [
      [['.gba', '.gb', '.gbc'], 'mgba'],
      [['.nds'], 'melonds'],
      [['.3ds', '.cci', '.cia'], 'azahar'],
      [['.nsp', '.xci', '.nro'], 'eden'],
      [['.wud', '.wux', '.wua'], 'cemu'],
      [['.rvz', '.wbfs', '.gcm', '.gcz', '.wii'], 'dolphin'],
      [['.sfc', '.smc'], 'bsnes'],
      [['.nes', '.fds', '.unf', '.unif'], 'mesen'],
      [['.n64', '.z64', '.v64'], 'mupen64plus'],
    ];

    if (/playstation[-_ ]?3|ps3/.test(normalized) && ['.iso', '.bin', '.cue'].includes(ext)) return 'rpcs3';
    if (/playstation[-_ ]?2|ps2/.test(normalized) && ['.iso', '.cso', '.chd', '.bin', '.cue', '.elf'].includes(ext)) return 'pcsx2';
    if (/xbox[-_ ]?360|x360/.test(normalized) && ['.iso', '.xex', '.xcp'].includes(ext)) return 'xenia-canary';
    if (/xbox[-_ ]?(original|classic)|xbox1/.test(normalized) && ext === '.iso') return 'xemu';
    if (/wii[-_ ]?u|wiiu/.test(normalized) && ['.iso', '.wud', '.wux', '.wua'].includes(ext)) return 'cemu';
    for (const [extensions, id] of rules) {
      if (extensions.includes(ext)) return id;
    }
    // Generic disc/container formats remain ambiguous unless their directory path
    // clearly identifies the intended platform. Never auto-map PKG/RAP/SELF files.
    if (['.chd', '.cso', '.pbp', '.iso', '.bin', '.cue'].includes(ext)) {
      if (/ps2|playstation[-_ ]?2/.test(normalized)) return 'pcsx2';
      if (/ps3|playstation[-_ ]?3/.test(normalized)) return 'rpcs3';
      if (/wii(?!u)|gamecube|gcube/.test(normalized)) return 'dolphin';
      if (/xbox/.test(normalized)) return 'xemu';
    }
    return null;
  }

  root.EmuStackLaunch = Object.freeze({ recommendEmulatorForGame });
})(globalThis);
