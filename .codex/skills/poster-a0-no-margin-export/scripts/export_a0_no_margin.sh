#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_ROOT=""
HTML_PATH="poster-gen/poster-preview.html"
PNG_PATH="poster-gen/poster-preview-output.png"
TRIMMED_PNG_PATH="poster-gen/poster-preview-output-bleed.png"
PDF_PATH="poster-gen/SIT_Copilot_Poster.pdf"
PDF_TITLE="SIT_Copilot_Poster"
VIEWPORT="3400,4804"
WAIT_MS="1200"
TRIM_THRESHOLD="6"
TRIM_COVERAGE="0.20"
TRIM_INSET="1"

usage() {
  cat <<'EOF'
Usage:
  export_a0_no_margin.sh [options]

Options:
  --repo-root PATH      Repository root (default: git toplevel or current directory)
  --html PATH           Source HTML path (default: poster-gen/poster-preview.html)
  --png PATH            Screenshot output PNG (default: poster-gen/poster-preview-output.png)
  --trimmed-png PATH    Trimmed PNG output (default: poster-gen/poster-preview-output-bleed.png)
  --pdf PATH            Output PDF path (default: poster-gen/SIT_Copilot_Poster.pdf)
  --title TEXT          PDF metadata title (default: SIT_Copilot_Poster)
  --viewport W,H        Screenshot viewport (default: 3400,4804)
  --wait-ms N           Wait time before screenshot in ms (default: 1200)
  --trim-threshold N    RGB distance threshold (default: 6)
  --trim-coverage R     Row/column content ratio threshold (default: 0.20)
  --trim-inset N        Extra inward crop in px (default: 1)
  -h, --help            Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      REPO_ROOT="$2"
      shift 2
      ;;
    --html)
      HTML_PATH="$2"
      shift 2
      ;;
    --png)
      PNG_PATH="$2"
      shift 2
      ;;
    --trimmed-png)
      TRIMMED_PNG_PATH="$2"
      shift 2
      ;;
    --pdf)
      PDF_PATH="$2"
      shift 2
      ;;
    --title)
      PDF_TITLE="$2"
      shift 2
      ;;
    --viewport)
      VIEWPORT="$2"
      shift 2
      ;;
    --wait-ms)
      WAIT_MS="$2"
      shift 2
      ;;
    --trim-threshold)
      TRIM_THRESHOLD="$2"
      shift 2
      ;;
    --trim-coverage)
      TRIM_COVERAGE="$2"
      shift 2
      ;;
    --trim-inset)
      TRIM_INSET="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$REPO_ROOT" ]]; then
  if git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    REPO_ROOT="$git_root"
  else
    REPO_ROOT="$PWD"
  fi
fi

resolve_path() {
  local value="$1"
  if [[ "$value" = /* ]]; then
    printf "%s" "$value"
  else
    printf "%s/%s" "$REPO_ROOT" "$value"
  fi
}

HTML_ABS="$(resolve_path "$HTML_PATH")"
PNG_ABS="$(resolve_path "$PNG_PATH")"
TRIMMED_PNG_ABS="$(resolve_path "$TRIMMED_PNG_PATH")"
PDF_ABS="$(resolve_path "$PDF_PATH")"

if [[ ! -f "$HTML_ABS" ]]; then
  echo "[ERROR] Source HTML not found: $HTML_ABS" >&2
  exit 1
fi

mkdir -p "$(dirname "$PNG_ABS")" "$(dirname "$TRIMMED_PNG_ABS")" "$(dirname "$PDF_ABS")"

echo "[1/4] Capture HTML -> PNG"
npx --yes playwright screenshot \
  --browser chromium \
  --full-page \
  --wait-for-timeout "$WAIT_MS" \
  --viewport-size "$VIEWPORT" \
  "file://$HTML_ABS" \
  "$PNG_ABS"

echo "[2/4] Trim outer border"
uv run --with pillow python "$SCRIPT_DIR/trim_uniform_border.py" \
  --input "$PNG_ABS" \
  --output "$TRIMMED_PNG_ABS" \
  --threshold "$TRIM_THRESHOLD" \
  --coverage "$TRIM_COVERAGE" \
  --inset "$TRIM_INSET"

TMP_HTML="$(mktemp /tmp/poster-a0-no-margin-XXXXXX.html)"
cleanup() {
  rm -f "$TMP_HTML"
}
trap cleanup EXIT

cat > "$TMP_HTML" <<EOF
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${PDF_TITLE}</title>
<style>
  @page { size: 841mm 1189mm; margin: 0; }
  html, body {
    margin: 0;
    padding: 0;
    width: 841mm;
    height: 1189mm;
    overflow: hidden;
    background: #fff;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }
  .page {
    width: 841mm;
    height: 1189mm;
    margin: 0;
    padding: 0;
  }
  img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: fill;
  }
</style>
</head>
<body>
  <div class="page">
    <img src="file://${TRIMMED_PNG_ABS}" alt="Poster" />
  </div>
</body>
</html>
EOF

echo "[3/4] Export A0 PDF"
npx --yes playwright pdf \
  --browser chromium \
  --paper-format A0 \
  --wait-for-timeout 800 \
  "file://$TMP_HTML" \
  "$PDF_ABS"

echo "[4/4] Verify output"
if command -v pdfinfo >/dev/null 2>&1; then
  pdfinfo "$PDF_ABS" | rg -n "Title:|Pages:|Page size:" -N || true
else
  echo "[WARN] pdfinfo not found; skipped verification"
fi

echo "[OK] Export complete: $PDF_ABS"
