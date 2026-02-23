/**
 * 12-Column Grid System for A0 Poster
 *
 * Based on design document specifications:
 * - 12-column grid with 6mm gutters
 * - 8mm row baseline for vertical rhythm
 * - 25mm outer margins
 */

import { mmToInches, A0_WIDTH, A0_HEIGHT } from './a0.js';

/** Number of columns in the grid */
export const COLUMNS = 12;

/** Gutter width in millimeters */
export const GUTTER_MM = 6;

/** Row baseline height in millimeters */
export const ROW_BASELINE_MM = 8;

/** Outer margin in millimeters */
export const MARGIN_MM = 25;

/** Gutter width in inches */
export const GUTTER_INCHES = mmToInches(GUTTER_MM);

/** Row baseline in inches */
export const ROW_BASELINE_INCHES = mmToInches(ROW_BASELINE_MM);

/** Outer margin in inches */
export const MARGIN_INCHES = mmToInches(MARGIN_MM);

/** Content width (A0 width minus margins) */
export const CONTENT_WIDTH = A0_WIDTH - MARGIN_INCHES * 2;

/** Content height (A0 height minus margins) */
export const CONTENT_HEIGHT = A0_HEIGHT - MARGIN_INCHES * 2;

/**
 * Calculate column width for a given column span
 * @param colSpan - Number of columns to span (1-12)
 * @return Width in inches
 */
export function colWidth(colSpan: number): number {
  if (colSpan < 1 || colSpan > COLUMNS) {
    throw new Error(`colSpan must be between 1 and ${COLUMNS}, got ${colSpan}`);
  }
  const gutterSpace = (colSpan - 1) * GUTTER_INCHES;
  const availableWidth = CONTENT_WIDTH - (COLUMNS - 1) * GUTTER_INCHES;
  const singleColWidth = availableWidth / COLUMNS;
  return singleColWidth * colSpan + gutterSpace;
}

/**
 * Calculate x position for a column index (0-based)
 * @param colIndex - Column index (0-11)
 * @return X position in inches from left edge
 */
export function colX(colIndex: number): number {
  if (colIndex < 0 || colIndex >= COLUMNS) {
    throw new Error(`colIndex must be between 0 and ${COLUMNS - 1}, got ${colIndex}`);
  }
  const availableWidth = CONTENT_WIDTH - (COLUMNS - 1) * GUTTER_INCHES;
  const singleColWidth = availableWidth / COLUMNS;
  return MARGIN_INCHES + colIndex * (singleColWidth + GUTTER_INCHES);
}

/**
 * Calculate height for multiple rows
 * @param rows - Number of rows
 * @return Height in inches
 */
export function rowHeight(rows: number): number {
  return rows * ROW_BASELINE_INCHES;
}

/**
 * Calculate y position for a row index (0-based)
 * @param rowIndex - Row index (0-based)
 * @return Y position in inches from top edge
 */
export function rowY(rowIndex: number): number {
  return MARGIN_INCHES + rowIndex * ROW_BASELINE_INCHES;
}

/**
 * Grid position definition
 */
export interface GridPosition {
  col: number;
  row: number;
  colSpan: number;
  rowSpan: number;
}

/**
 * Calculate box dimensions from grid position
 * @param pos - Grid position
 * @return Box with x, y, w, h in inches
 */
export function gridToBox(pos: GridPosition): { x: number; y: number; w: number; h: number } {
  return {
    x: colX(pos.col),
    y: rowY(pos.row),
    w: colWidth(pos.colSpan),
    h: rowHeight(pos.rowSpan),
  };
}

/**
 * Standard section heights (in inches) based on design document
 */
export const SECTION_HEIGHTS = {
  header: mmToInches(170),  // 170mm header height
  fullRow: 0,               // Calculated dynamically
} as const;
