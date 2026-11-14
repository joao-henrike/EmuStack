'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const experience = require('../web/experience.js');

const defaults = {tv:false, gamepad:true, contrast:false, reduceMotion:false};
assert.deepEqual(experience.normalizePreferences(null), defaults);
assert.deepEqual(experience.parsePreferences('{bad json'), defaults);
assert.deepEqual(experience.parsePreferences('[]'), defaults);
assert.deepEqual(experience.parsePreferences('{"tv":true,"gamepad":"false","contrast":true,"extra":1}'),
  {tv:true, gamepad:true, contrast:true, reduceMotion:false});
assert.equal(experience.nextFocusIndex(0, 0, 1), -1);
assert.equal(experience.nextFocusIndex(4, -1, 1), 0);
assert.equal(experience.nextFocusIndex(4, -1, -1), 3);
assert.equal(experience.nextFocusIndex(4, 3, 1), 0);
assert.equal(experience.nextFocusIndex(4, 0, -1), 3);
assert.equal(experience.nextFocusIndex(4, 1, 1), 2);
function pad(button, axes = [0, 0]) {
  return {connected:true, axes, buttons:Array.from({length:16}, (_,index) => ({pressed:index === button}))};
}
assert.equal(experience.gamepadIntent(null), null);
assert.equal(experience.gamepadIntent({connected:false, buttons:[]}), null);
for (const [button, expected] of [
  [0,'activate'], [1,'back'], [9,'settings'],
  [12,'previous'], [14,'previous'], [13,'next'], [15,'next']
]) assert.equal(experience.gamepadIntent(pad(button)), expected);
assert.equal(experience.gamepadIntent(pad(-1, [-0.9, 0])), 'previous');
assert.equal(experience.gamepadIntent(pad(-1, [0.9, 0])), 'next');
assert.equal(experience.gamepadIntent(pad(-1, [0.3, 0.2])), null);
const html = fs.readFileSync(path.join(root, 'web/index.html'), 'utf8');
const app = fs.readFileSync(path.join(root, 'web/app.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'web/app.css'), 'utf8');
const ids = [
  'tv-mode-toggle','experience-settings','experience-dialog','experience-tv',
  'experience-gamepad','experience-contrast','experience-motion',
  'experience-fullscreen','experience-gamepad-status','close-experience',
  'view-sessions','session-filter','session-center-list','session-total',
  'session-running','session-finished','refresh-session-center'
];
for (const id of ids) assert.ok(html.includes('id="' + id + '"'), 'missing UI element: ' + id);
assert.ok(html.indexOf('/assets/experience.js') < html.indexOf('/assets/app.js'));
assert.match(app, /window\.EmuStackExperience\.init/);
assert.match(app, /filter === 'running'/);
assert.match(app, /data-stop-process/);
assert.match(css, /\.tv-mode/);
assert.match(css, /\.experience-contrast/);
assert.match(css, /prefers-reduced-motion:reduce/);
assert.doesNotMatch(fs.readFileSync(path.join(root, 'web/experience.js'), 'utf8'),
  /\/var\/run\/docker\.sock|child_process|execSync|\/dev\/dri|docker compose/i);
console.log('Phase 2 browser/gamepad/session contracts passed.');
