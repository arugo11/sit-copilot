/**
 * A0 Poster Dimensions
 *
 * A0 size: 841 x 1189 mm (33.1 x 46.8 inches)
 * Portrait orientation for academic posters
 */

/** A0 width in inches */
export const A0_WIDTH = 33.1;

/** A0 height in inches */
export const A0_HEIGHT = 46.8;

/** A0 layout definition */
export const A0_LAYOUT = {
  name: 'A0',
  width: A0_WIDTH,
  height: A0_HEIGHT,
} as const;

/** A0 dimensions in millimeters */
export const A0_WIDTH_MM = 841;
export const A0_HEIGHT_MM = 1189;

/**
 * Convert millimeters to inches
 * @param mm - Value in millimeters
 * @return Value in inches
 */
export function mmToInches(mm: number): number {
  return mm / 25.4;
}

/**
 * Convert inches to millimeters
 * @param inches - Value in inches
 * @return Value in millimeters
 */
export function inchesToMm(inches: number): number {
  return inches * 25.4;
}
