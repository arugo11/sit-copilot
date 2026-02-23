/**
 * Box/Container Component
 *
 * Renders rectangular shapes with optional fill and border.
 * Used for section backgrounds, dividers, and containers.
 */

import type { Box, Slide } from '../../domain/types.js';
import { COLORS } from '../../theme/colors.js';

/**
 * Box rendering options
 */
export interface BoxOptions {
  /** Fill color (hex code, with/without #) */
  fill?: string;
  /** Border options */
  border?: { color: string; width: number };
  /** Corner radius in inches (0 = square) */
  cornerRadius?: number;
  /** Shadow effect */
  shadow?: boolean;
}

/**
 * Box/Container component class
 */
export class BoxComponent {
  private readonly pptx: { shapes: { RECTANGLE: string } };
  private readonly options: BoxOptions;

  constructor(pptx: { shapes: { RECTANGLE: string } }, options: BoxOptions = {}) {
    this.pptx = pptx;
    this.options = options;
  }

  /**
   * Measure placeholder dimensions
   * Actual dimensions are determined by the container
   */
  measure(): Box {
    return { x: 0, y: 0, w: 1, h: 1 };
  }

  /**
   * Render box to a slide
   */
  render(box: Box, slide: Slide): void {
    const fill = this.options.fill || COLORS.white;
    const fillColor = fill.startsWith('#') ? fill.slice(1) : fill;

    const border = this.options.border
      ? {
          color: this.options.border.color.startsWith('#')
            ? this.options.border.color.slice(1)
            : this.options.border.color,
          width: this.options.border.width,
          type: 'solid' as const,
        }
      : { type: 'none' as const, color: 'FFFFFF', width: 0 };

    slide.addShape(this.pptx.shapes.RECTANGLE, {
      x: box.x,
      y: box.y,
      w: box.w,
      h: box.h,
      fill: { color: fillColor },
      line: border,
      radius: this.options.cornerRadius || 0,
      shadow: this.options.shadow
        ? {
            type: 'outer',
            blur: 3,
            offset: 2,
            color: '00000033',
            angle: 270,
          }
        : undefined,
    });
  }
}

/**
 * Create a section background box
 */
export function createSectionBox(
  pptx: { shapes: { RECTANGLE: string } },
  fill = COLORS.white,
): BoxComponent {
  return new BoxComponent(pptx, {
    fill,
    border: { color: COLORS.border, width: 1 },
  });
}

/**
 * Create a divider line box
 */
export function createDivider(
  pptx: { shapes: { RECTANGLE: string } },
  color = COLORS.border,
): BoxComponent {
  return new BoxComponent(pptx, {
    fill: color,
    border: undefined,
  });
}
