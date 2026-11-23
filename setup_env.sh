#!/usr/bin/env bash
# Окружение тулкита презентаций (идемпотентно: повторный запуск только докачивает недостающее).
#
#   ./setup_env.sh            # Python venv + npm + Chromium + шрифты Google Fonts + самопроверка
#   ./setup_env.sh --assets   # + исходники для пересборки картинок практической презентации (карты, иконки)
#
# Нужен доступ только к: pypi.org, registry.npmjs.org, github.com (без apt, без sudo).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
T0=$(date +%s)
say() { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }

# 1) Python
say "Python venv (.venv)"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt

# 2) Node: LibreOffice (WASM) для рендера PPTX/DOCX/XLSX + Chromium для скриншотов
say "npm install (libreoffice-kit, @sparticuz/chromium)"
if [ ! -d node_modules/@deepseek-ai/libreoffice-kit ] || [ ! -d node_modules/@sparticuz/chromium ]; then
  npm ci --no-audit --no-fund --loglevel=error || npm install --no-audit --no-fund --loglevel=error
fi

say "Chromium → .cache/chromium"
.venv/bin/python tools/setup_chromium.py

# 3) Шрифты: разреженный клон github.com/google/fonts (только нужные семейства) + статические начертания
say "Шрифты Google Fonts → .cache/fonts"
GF=.cache/src/gfonts
if [ ! -d "$GF/.git" ]; then
  mkdir -p .cache/src
  git clone -q --depth 1 --filter=blob:none --sparse https://github.com/google/fonts "$GF"
fi
tr '\n' '\0' < tools/env/gfonts.txt | xargs -0 git -C "$GF" sparse-checkout set --no-cone
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, ".")
from pptkit.fonts import install_toolkit_fonts
install_toolkit_fonts(verbose=True)
PY

# 4) (опционально) исходники ассетов практической презентации
if [ "${1:-}" = "--assets" ]; then
  say "Natural Earth (карты) + Fluent Emoji (иконки)"
  if [ ! -d .cache/src/ne/.git ]; then
    git clone -q --depth 1 --filter=blob:none --sparse https://github.com/nvkelso/natural-earth-vector .cache/src/ne
  fi
  tr '\n' '\0' < tools/env/naturalearth.txt | xargs -0 git -C .cache/src/ne sparse-checkout set --no-cone
  if [ ! -d .cache/src/fluent/.git ]; then
    git clone -q --depth 1 --filter=blob:none --sparse https://github.com/microsoft/fluentui-emoji .cache/src/fluent
  fi
  tr '\n' '\0' < tools/env/fluent.txt | xargs -0 git -C .cache/src/fluent sparse-checkout set --no-cone
fi

# 5) Самопроверка: скриншот HTML-строки + рендер тестового слайда
say "Самопроверка"
.venv/bin/python tools/snap.py --html "<div style='font:900 56px Nunito;padding:30px;color:#0E2A47'>Тулкит готов ✓</div>" \
  --viewport 700x160 -q -o checks/runs/selftest >/dev/null
echo "  ✔ Chromium: checks/runs/selftest/html.png"
if [ -f presentations/drevnyaya-gretsiya.pptx ]; then
  .venv/bin/python tools/snap.py presentations/drevnyaya-gretsiya.pptx --slides 1 -q -o checks/runs/selftest >/dev/null
  echo "  ✔ LibreOffice: checks/runs/selftest/drevnyaya-gretsiya/slide-01.png"
fi
echo "Готово за $(( $(date +%s) - T0 )) с. Инструменты: tools/*.py (см. README.md)"
