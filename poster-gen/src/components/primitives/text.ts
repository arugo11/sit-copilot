/**
 * Text Component
 *
 * Renders text content to poster slides with configurable styling.
 */

import type { Box, Slide } from '../../domain/types.js';
import { COLORS } from '../../theme/colors.js';
import { FONTS, FONT_FAMILIES } from '../../theme/typography.js';
import type { TextStyle } from '../../theme/typography.js';

/**
 * Text rendering options
 */
export interface TextOptions {
  /** Text content (string or array for bullet points) */
  text: string | string[];
  /** Font size in points (defaults to body size) */
  fontSize?: number;
  /** Text color (hex code, with/without #) */
  color?: string;
  /** Bold text */
  bold?: boolean;
  /** Italic text */
  italic?: boolean;
  /** Underline text */
  underline?: boolean;
  /** Horizontal alignment */
  align?: 'left' | 'center' | 'right' | 'justify';
  /** Vertical alignment */
  valign?: 'top' | 'middle' | 'bottom';
  /** Font face/family */
  fontFace?: string;
  /** Line spacing (1.0 = single, 2.0 = double) */
  lineSpacing?: number;
}

/**
 * Text component class
 */
export class TextComponent {
  private readonly options: TextOptions;

  constructor(_pptx: unknown, options: TextOptions) {
    this.options = options;
  }

  /**
   * Estimate dimensions for this text
   * Note: This is an approximation as PptxGenJS doesn't provide text measurement
   */
  measure(): Box {
    const fontSize = this.options.fontSize || FONTS.body;
    const charWidth = fontSize * 0.6; // Approximate character width in inches
    const lineHeight = fontSize / 72; // Convert pt to inches

    const text = typeof this.options.text === 'string'
      ? this.options.text
      : this.options.text.join('\n');
    const lines = Math.ceil(text.length / 50); // Approximate line wrapping

    return {
      x: 0,
      y: 0,
      w: Math.min(charWidth * 50, 30), // Max 30 inches width
      h: lineHeight * lines * 1.2, // 1.2 for line spacing
    };
  }

  /**
   * Render text to a slide
   */
  render(box: Box, slide: Slide): void {
    const color = this.options.color || COLORS.text;
    // Remove # from color if present for PptxGenJS
    const colorValue = color.startsWith('#') ? color.slice(1) : color;

    // Convert array to newline-separated string for proper rendering
    const textValue = Array.isArray(this.options.text)
      ? this.options.text.join('\n')
      : this.options.text;

    slide.addText(textValue, {
      x: box.x,
      y: box.y,
      w: box.w,
      h: box.h,
      fontSize: this.options.fontSize || FONTS.body,
      color: colorValue,
      bold: this.options.bold || false,
      italic: this.options.italic || false,
      underline: this.options.underline || false,
      align: this.options.align || 'left',
      valign: this.options.valign || 'top',
      fontFace: this.options.fontFace || FONT_FAMILIES.primary,
      lineSpacingMultiple: this.options.lineSpacing || 1.2,
    });
  }
}

/**
 * Create a styled text component with predefined style
 */
export function createStyledText(
  pptx: unknown,
  text: string | string[],
  style: TextStyle,
): TextComponent {
  return new TextComponent(pptx, {
    text,
    fontSize: style.fontSize,
    color: style.color,
    bold: style.bold,
    italic: style.italic,
    underline: style.underline,
    align: style.align,
    valign: style.valign,
    fontFace: style.fontFace,
  });
}
