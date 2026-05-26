#!/bin/bash
set +e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

APP_PY="$SCRIPT_DIR/HVT_LAN.py"
LOGIC_PY="$SCRIPT_DIR/HVT_final.py"
REQ_FILE="$SCRIPT_DIR/requirements_hvt.txt"
VENV_DIR="$SCRIPT_DIR/.venv"

pick_python() {
  if [ -x "$VENV_DIR/bin/python3" ]; then echo "$VENV_DIR/bin/python3"; return; fi
  for v in 3.13 3.12 3.11 3.10 3.14; do
    if command -v "python$v" >/dev/null 2>&1; then command -v "python$v"; return; fi
  done
  if command -v python3 >/dev/null 2>&1; then command -v python3; return; fi
  if command -v python >/dev/null 2>&1; then command -v python; return; fi
  echo ""
}

BASE_PY="$(pick_python)"

if [ ! -f "$APP_PY" ]; then
  echo "[ERROR] HVT_LAN.py not found."
  echo "Expected: $APP_PY"
  read -r -p "Press Enter to exit..." _
  exit 1
fi

if [ ! -f "$LOGIC_PY" ]; then
  echo "[ERROR] HVT_final.py not found."
  echo "Expected: $LOGIC_PY"
  read -r -p "Press Enter to exit..." _
  exit 1
fi

if [ -z "$BASE_PY" ]; then
  echo "[ERROR] Python was not found."
  echo "Install Python 3 and run this launcher again."
  read -r -p "Press Enter to exit..." _
  exit 1
fi

PY_VER="$($BASE_PY -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
echo "[INFO] Python found: $BASE_PY"
echo "[INFO] Python version: $PY_VER"

if [ ! -f "$REQ_FILE" ]; then
  cat > "$REQ_FILE" <<'REQ'
networkx
matplotlib
REQ
fi

if [ ! -x "$VENV_DIR/bin/python3" ]; then
  echo "[INFO] Creating virtual environment..."
  "$BASE_PY" -m venv "$VENV_DIR" || {
    echo "[ERROR] Failed to create .venv"
    read -r -p "Press Enter to exit..." _
    exit 1
  }
fi

RUN_PY="$VENV_DIR/bin/python3"
if [ ! -x "$RUN_PY" ]; then
  RUN_PY="$BASE_PY"
fi

echo "[INFO] Upgrading pip, setuptools, wheel..."
"$RUN_PY" -m pip install --upgrade pip setuptools wheel || echo "[WARN] pip bootstrap upgrade failed. Continuing..."

echo "[INFO] Installing required packages: networkx, matplotlib"
"$RUN_PY" -m pip install --default-timeout 120 networkx matplotlib || {
  echo "[ERROR] Failed to install required packages."
  read -r -p "Press Enter to exit..." _
  exit 1
}

"$RUN_PY" -c 'import tkinter' >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "[WARN] tkinter is not available in this Python environment."
  echo "[WARN] Reinstall Python with Tk support if the GUI cannot open."
fi

echo "[INFO] Skipping pygame installation."
echo "[INFO] This launcher is intended for the LAN/Tk workflow."

echo
echo "[INFO] Using Python: $RUN_PY"
echo "[INFO] Starting HVT..."
echo "[INFO] In the GUI you can choose host/join and attacker/defender."
echo
"$RUN_PY" "$APP_PY" --logic "$LOGIC_PY"
EXITCODE=$?

echo
echo "[INFO] Program exited with code: $EXITCODE"
read -r -p "Press Enter to close this window..." _
exit $EXITCODE
