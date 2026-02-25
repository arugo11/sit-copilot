---
name: poster-a0-no-margin-export
description: Export A0 poster PDFs with zero page margin while preserving WebUI appearance by using screenshot, border-trim, and full-page PDF rendering. Use when users ask "A0 PDF", "余白なし", "webと同じ見た目", or poster HTML print delivery.
---

# Poster A0 No Margin Export

Use this skill to generate print-ready A0 PDF from poster HTML with no outer margin and WebUI-like appearance.

## When To Use

- User asks for:
  - "A0 PDF"
  - "余白なしで出力"
  - "WebUIと同じ見た目でPDF化"
  - "poster-preview.html から印刷用PDFを作る"

## Inputs

- Default source HTML: `poster-gen/poster-preview.html`
- Default preview PNG: `poster-gen/poster-preview-output.png`
- Default trimmed PNG: `poster-gen/poster-preview-output-bleed.png`
- Default output PDF: `poster-gen/SIT_Copilot_Poster.pdf`
- Default PDF title: `SIT_Copilot_Poster`

## Workflow

1. Render poster HTML to PNG using Playwright screenshot (`--viewport-size 3400,4804`).
2. Trim uniform outer border from PNG (background color sampled from top-left pixel).
3. Compose temporary A0 HTML (`@page` margin 0) with trimmed PNG stretched to full page.
4. Export single-page A0 PDF via Playwright PDF.
5. Verify PDF (`Pages: 1`, `Page size: A0`) with `pdfinfo`.

## Command

```bash
bash .codex/skills/poster-a0-no-margin-export/scripts/export_a0_no_margin.sh \
  --repo-root /home/argo/sit-copilot \
  --html poster-gen/poster-preview.html \
  --pdf poster-gen/SIT_Copilot_Poster.pdf \
  --title SIT_Copilot_Poster
```

## Script Parameters

- `--repo-root`: repository root (default: current git root)
- `--html`: source HTML path (relative to repo root or absolute)
- `--png`: screenshot output path
- `--trimmed-png`: trimmed output path
- `--pdf`: output PDF path
- `--title`: PDF metadata title
- `--viewport`: screenshot viewport (`W,H`)
- `--wait-ms`: screenshot wait time (ms)
- `--trim-threshold`: RGB distance threshold for border detection
- `--trim-coverage`: row/column coverage ratio for content detection
- `--trim-inset`: inward crop pixels after detection

## Guardrails

- Keep poster claims/metrics unchanged unless explicitly requested.
- Do not add URL text to print output when QR-only policy is requested.
- Prefer HTML edits in source file; avoid manual PPTX edits unless unavoidable.

## Output Contract

- Produce:
  - `poster-gen/poster-preview-output.png`
  - `poster-gen/poster-preview-output-bleed.png`
  - target A0 PDF path
- Report:
  - PDF path
  - `pdfinfo` summary lines (`Title`, `Pages`, `Page size`)

## Files

- `scripts/export_a0_no_margin.sh`
- `scripts/trim_uniform_border.py`
