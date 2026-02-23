/**
 * Core domain types for poster generation
 */

/**
 * Box dimensions and position
 * All measurements are in inches for PptxGenJS
 */
export interface Box {
  /** X position in inches */
  x: number;
  /** Y position in inches */
  y: number;
  /** Width in inches */
  w: number;
  /** Height in inches */
  h: number;
}

/**
 * Slide type from PptxGenJS
 * Minimal interface for rendering operations
 */
export interface Slide {
  addText(text: unknown, options: unknown): unknown;
  addShape(shape: unknown, options: unknown): unknown;
  addImage(options: unknown): unknown;
}

/**
 * Component contract for renderable elements
 * All components must implement this interface
 */
export interface Component {
  /**
   * Calculate the dimensions this component requires
   * @return Box with width and height (x, y may be 0)
   */
  measure(): Box;

  /**
   * Render the component to a slide
   * @param box - Position and dimensions for rendering
   * @param slide - PptxGenJS slide object
   */
  render(box: Box, slide: Slide): void;
}

/**
 * Alignment options for component positioning
 */
export type Alignment = 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom';

/**
 * Spacing definition
 */
export interface Spacing {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

/**
 * Default spacing values (in inches)
 */
export const DEFAULT_SPACING: Spacing = {
  top: 0.2,
  right: 0.2,
  bottom: 0.2,
  left: 0.2,
};

/**
 * Theme variant selection
 */
export type ThemeVariant = 'technical-blue' | 'minimal' | 'academic';

// Re-export poster content types from schema.ts to maintain consistency
export type {
  PosterContent,
  PosterMeta,
  PosterSections,
  AIFlowItem,
  PromptExample,
  MetricItem,
  BackgroundSection,
  ObjectivesSection,
  AIUsageSection,
  ResultsSection,
  FuturePlansSection,
} from './schema.js';
