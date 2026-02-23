/**
 * Image Component
 *
 * Renders images to poster slides with configurable sizing.
 */

import type { Box, Slide } from '../../domain/types.js';

/**
 * Image sizing options
 */
export type ImageSizing = 'cover' | 'contain' | 'exact' | 'stretch';

/**
 * Image rendering options
 */
export interface ImageOptions {
  /** Path to image file (local or URL) */
  path: string;
  /** Sizing mode for the image */
  sizing?: ImageSizing;
  /** Whether to maintain aspect ratio */
  maintainAspectRatio?: boolean;
  /** Rotation angle in degrees */
  rotation?: number;
  /** Transparency (0-100, where 100 is fully transparent) */
  transparency?: number;
}

/**
 * Image component class
 */
export class ImageComponent {
  private readonly options: ImageOptions;

  constructor(_pptx: unknown, options: ImageOptions) {
    this.options = options;
  }

  /**
   * Measure placeholder dimensions
   * Actual size depends on the image and container
   */
  measure(): Box {
    // Return placeholder - actual size depends on image
    return { x: 0, y: 0, w: 5, h: 3 };
  }

  /**
   * Render image to a slide
   */
  render(box: Box, slide: Slide): void {
    const sizing: { type: string; w: number; h: number } = {
      type: this.options.sizing || 'contain',
      w: box.w,
      h: box.h,
    };

    slide.addImage({
      path: this.options.path,
      x: box.x,
      y: box.y,
      w: box.w,
      h: box.h,
      sizing: this.options.maintainAspectRatio !== false ? sizing : undefined,
      rotate: this.options.rotation || 0,
      transparency: this.options.transparency || 0,
    });
  }
}

/**
 * Create a logo image component
 */
export function createLogo(
  pptx: unknown,
  path: string,
  _maxSize = 1.5,
): ImageComponent {
  return new ImageComponent(pptx, {
    path,
    sizing: 'contain',
    maintainAspectRatio: true,
  });
}
