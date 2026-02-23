/**
 * Color Palette for SIT Copilot Poster
 *
 * Technical Blue Theme based on design document
 */

/**
 * Main color palette
 * All colors are const assertions for type safety
 */
export const COLORS = {
  /** Primary dark navy for headers and backgrounds */
  primary: '#0F2742',
  /** Secondary blue for flow diagrams and links */
  secondary: '#1F6FEB',
  /** Secondary teal for Q&A flow and accents */
  secondary2: '#14B8A6',
  /** Accent amber for KPIs and highlights (max 10% usage) */
  accent: '#F59E0B',
  /** Text color for body text */
  text: '#1F2937',
  /** Background color for poster */
  background: '#F7F9FC',
  /** Border color for section borders */
  border: '#E5E7EB',
  /** White for backgrounds and highlights */
  white: '#FFFFFF',
  /** Light gray for subtle backgrounds */
  lightGray: '#F3F4F6',
  /** Medium gray for secondary text */
  mediumGray: '#6B7280',
} as const;

/**
 * Color type derived from COLORS object
 */
export type Color = typeof COLORS[keyof typeof COLORS];

/**
 * Section-specific color schemes
 */
export const SECTION_COLORS = {
  background: {
    fill: COLORS.white,
    border: COLORS.border,
  },
  primary: {
    fill: COLORS.primary,
    text: COLORS.white,
  },
  accent: {
    fill: COLORS.accent,
    text: COLORS.text,
  },
} as const;

/**
 * KPI metric colors (for performance indicators)
 */
export const KPI_COLORS = {
  positive: '#10B981',  // Green
  neutral: '#6366F1',   // Indigo
  warning: '#F59E0B',   // Amber
  danger: '#EF4444',    // Red
} as const;

/**
 * Flow diagram colors for AI Usage section
 */
export const FLOW_COLORS = {
  speech: '#3B82F6',    // Blue
  slide: '#8B5CF6',     // Purple
  question: '#EC4899',  // Pink
  asr: '#14B8A6',       // Teal
  ocr: '#F59E0B',       // Amber
  search: '#6366F1',    // Indigo
  llm: '#8B5CF6',       // Purple
  caption: '#10B981',   // Green
  answer: '#3B82F6',    // Blue
} as const;
