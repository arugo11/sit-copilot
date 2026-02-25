#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def pixel_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def find_content_bbox(
    image: Image.Image,
    threshold: int,
    coverage: float,
) -> tuple[int, int, int, int] | None:
    rgb = image.convert("RGB")
    width, height = rgb.size
    bg = rgb.getpixel((0, 0))

    min_col_hits = int(height * coverage)
    min_row_hits = int(width * coverage)

    content_cols: list[int] = []
    for x in range(width):
        hits = 0
        for y in range(height):
            if pixel_distance(rgb.getpixel((x, y)), bg) > threshold:
                hits += 1
        if hits > min_col_hits:
            content_cols.append(x)

    content_rows: list[int] = []
    for y in range(height):
        hits = 0
        for x in range(width):
            if pixel_distance(rgb.getpixel((x, y)), bg) > threshold:
                hits += 1
        if hits > min_row_hits:
            content_rows.append(y)

    if not content_cols or not content_rows:
        return None

    left = min(content_cols)
    right = max(content_cols) + 1
    top = min(content_rows)
    bottom = max(content_rows) + 1
    return left, top, right, bottom


def apply_inset(
    bbox: tuple[int, int, int, int],
    inset: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    if inset <= 0:
        return bbox

    max_inset_x = max(0, (right - left - 2) // 2)
    max_inset_y = max(0, (bottom - top - 2) // 2)
    safe_inset = min(inset, max_inset_x, max_inset_y)

    return (
        left + safe_inset,
        top + safe_inset,
        right - safe_inset,
        bottom - safe_inset,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim uniform outer border from poster screenshot.",
    )
    parser.add_argument("--input", required=True, help="Input PNG path")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument(
        "--threshold",
        type=int,
        default=6,
        help="Color distance threshold (default: 6)",
    )
    parser.add_argument(
        "--coverage",
        type=float,
        default=0.20,
        help="Required non-background ratio per row/column (default: 0.20)",
    )
    parser.add_argument(
        "--inset",
        type=int,
        default=1,
        help="Extra inward crop pixels after detection (default: 1)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    image = Image.open(input_path)
    bbox = find_content_bbox(
        image=image,
        threshold=args.threshold,
        coverage=args.coverage,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if bbox is None:
        image.save(output_path)
        print(f"[WARN] Content bbox not found. Copied image as-is: {output_path}")
        return

    cropped_bbox = apply_inset(bbox, args.inset)
    cropped = image.crop(cropped_bbox)
    cropped.save(output_path)

    print(f"[OK] Trimmed: {input_path}")
    print(f"     bbox(raw): {bbox}")
    print(f"     bbox(final): {cropped_bbox}")
    print(f"     size: {cropped.size[0]}x{cropped.size[1]}")
    print(f"     output: {output_path}")


if __name__ == "__main__":
    main()
