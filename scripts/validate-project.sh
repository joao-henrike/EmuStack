#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
printf '\n== Python unit/regression tests ==\n'
python3 -m unittest discover -s tests -v
printf '\n== Python syntax ==\n'
python3 -m compileall -q emustack.py webapp.py console_modes.py console_agent.py scripts tests
python3 scripts/check-release-lock.py release-lock.json
printf '\n== Auditoria dos 24 fontes upstream ==\n'
python3 scripts/upstream-manager.py audit
printf 'Python syntax OK.\n'
if command -v node >/dev/null 2>&1; then
  printf '\n== JavaScript syntax and launch recommendation tests ==\n'
  node --check web/app.js
  node --check web/launch-utils.js
  node --check web/experience.js
  node tests/test_experience.js
  node tests/test_launch_utils.js
  node tests/test_console_ui.js
else
  echo 'AVISO: Node.js não encontrado; testes JavaScript foram pulados.' >&2
fi
printf '\n== Shell syntax ==\n'
for script in scripts/host-setup.sh scripts/install-available-apt.sh; do sh -n "$script"; done
for script in scripts/build-and-audit.sh scripts/validate-project.sh scripts/freeze-upstream-lock.sh scripts/runtime-acceptance.sh scripts/build-phase1-isolated.sh scripts/phase1.sh scripts/phase1-acceptance.sh; do bash -n "$script"; done
printf 'Shell syntax OK.\n'
