/**
 * Typography System for A0 Poster
 *
 * Font sizes optimized for 1-2m viewing distance
 * Based on design document specifications
 */

/**
 * Font sizes in points (for PowerPoint)
 */
export const FONTS = {
  /** Main poster title */
  title: 120,
  /** Subtitle below title */
  subtitle: 72,
  /** Author names */
  authors: 48,
  /** Section headers */
  section: 64,
  /** Body text */
  body: 30,
  /** Caption text */
  caption: 24,
  /** Subsection headers */
  subsection: 42,
  /** Small text for footnotes */
  small: 20,
} as const;

/**
 * Font families
 */
export const FONT_FAMILIES = {
  /** Primary font for Japanese text */
  primary: 'Noto Sans JP',
  /** Secondary font for English and numbers */
  secondary: 'Inter',
  /** Monospace font for code and prompts */
  mono: 'JetBrains Mono',
  /** Fallback sans-serif */
  fallback: 'Arial',
} as const;

/**
 * Font weight options
 */
export const FONT_WEIGHT = {
  normal: 400,
  medium: 500,
  semiBold: 600,
  bold: 700,
} as const;

/**
 * Text alignment options
 */
export type TextAlign = 'left' | 'center' | 'right' | 'justify';

/**
 * Vertical alignment options
 */
export type VAlign = 'top' | 'middle' | 'bottom';

/**
 * Font size type
 */
export type FontSize = typeof FONTS[keyof typeof FONTS];

/**
 * Font family type
 */
export type FontFamily = typeof FONT_FAMILIES[keyof typeof FONT_FAMILIES];

/**
 * Typography style definition
 */
export interface TextStyle {
  fontSize?: number;
  fontFace?: string;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  color?: string;
  align?: TextAlign;
  valign?: VAlign;
}

/**
 * Predefined typography styles
 */
export const TEXT_STYLES = {
  title: {
    fontSize: FONTS.title,
    fontFace: FONT_FAMILIES.primary,
    bold: true,
    color: '#0F2742',
    align: 'center' as TextAlign,
  },
  subtitle: {
    fontSize: FONTS.subtitle,
    fontFace: FONT_FAMILIES.primary,
    bold: false,
    color: '#1F2937',
    align: 'center' as TextAlign,
  },
  authors: {
    fontSize: FONTS.authors,
    fontFace: FONT_FAMILIES.primary,
    bold: false,
    color: '#374151',
    align: 'center' as TextAlign,
  },
  sectionHeader: {
    fontSize: FONTS.section,
    fontFace: FONT_FAMILIES.primary,
    bold: true,
    color: '#0F2742',
  },
  body: {
    fontSize: FONTS.body,
    fontFace: FONT_FAMILIES.primary,
    bold: false,
    color: '#1F2937',
  },
  caption: {
    fontSize: FONTS.caption,
    fontFace: FONT_FAMILIES.primary,
    bold: false,
    color: '#6B7280',
  },
  code: {
    fontSize: FONTS.body,
    fontFace: FONT_FAMILIES.mono,
    bold: false,
    color: '#374151',
  },
} as const;
