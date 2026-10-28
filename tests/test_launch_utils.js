'use strict';
const assert = require('node:assert/strict');
require('../web/launch-utils.js');
const recommend = globalThis.EmuStackLaunch.recommendEmulatorForGame;

const cases = [
  ['homebrew/demo.gba', 'mgba'],
  ['library/nds/game.nds', 'melonds'],
  ['games/PS2/Gran Turismo.iso', 'pcsx2'],
  ['games/PS3/Disc.iso', 'rpcs3'],
  ['games/WiiU/Zelda.iso', 'cemu'],
  ['games/Xbox 360/title.xex', 'xenia-canary'],
  ['games/Switch/title.nsp', 'eden'],
  ['games/unknown/disc.iso', null],
  ['games/unknown/disc.bin', null],
  ['games/PS3/license.pkg', null],
  ['games/PS3/license.rap', null],
  ['games/PS3/title.self', null],
];
for (const [path, expected] of cases) {
  assert.equal(recommend(path), expected, `recommend(${path})`);
}
assert.equal(recommend('C:\\games\\PS2\\game.cue'), 'pcsx2');
console.log(`Launch recommendation tests passed (${cases.length + 1} cases).`);
