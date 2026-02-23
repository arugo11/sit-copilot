/**
 * PptxGenJS Adapter
 *
 * Wrapper around PptxGenJS for A0 poster generation.
 * Handles initialization, master slides, and slide creation.
 */

import PptxGenJS from 'pptxgenjs';
import { A0_WIDTH, A0_HEIGHT } from '../layout/a0.js';
import { COLORS } from '../theme/colors.js';

/**
 * PptxGenJS shape types
 */
export const SHAPES = {
  RECTANGLE: 'RECTANGLE',
  LINE: 'LINE',
  ELLIPSE: 'ELLIPSE',
} as const;

/**
 * PptxInstance interface for components
 * Provides minimal interface that components expect
 */
export interface PptxInstance {
  shapes: typeof SHAPES;
}

/**
 * PptxGenJS adapter class
 */
export class PptxAdapter {
  private readonly pptx: PptxGenJS;
  private readonly pptxInstance: PptxInstance;

  constructor() {
    this.pptx = new PptxGenJS();

    // Define A0 custom layout
    this.pptx.defineLayout({
      name: 'A0',
      width: A0_WIDTH,
      height: A0_HEIGHT,
    });
    this.pptx.layout = 'A0';

    // Set presentation metadata
    this.pptx.author = 'SIT Copilot Team';
    this.pptx.title = 'SIT Copilot Poster';
    this.pptx.subject = 'AI Innovators Cup @ Shibaura 2026';

    // Create a PptxInstance wrapper for components
    this.pptxInstance = {
      shapes: SHAPES,
    };

    // Setup master slide
    this.setupMasterSlide();
  }

  /**
   * Define master slide with common elements
   */
  private setupMasterSlide(): void {
    // Remove '#' from color for PptxGenJS
    const bgColor = COLORS.background.startsWith('#')
      ? COLORS.background.slice(1)
      : COLORS.background;

    const primaryColor = COLORS.primary.startsWith('#')
      ? COLORS.primary.slice(1)
      : COLORS.primary;

    this.pptx.defineSlideMaster({
      title: 'POSTER_MASTER',
      background: { color: bgColor },
      objects: [
        {
          // Footer line with event name
          text: {
            text: 'AI Innovators Cup @ Shibaura 2026',
            options: {
              x: 0,
              y: A0_HEIGHT - 0.5,
              w: '100%',
              h: 0.4,
              align: 'center',
              color: primaryColor,
              fontSize: 18,
              fontFace: 'Arial',
            },
          },
        },
      ],
    });
  }

  /**
   * Create a new slide using the master slide
   */
  createSlide(): PptxGenJS.Slide {
    return this.pptx.addSlide({ masterName: 'POSTER_MASTER' });
  }

  /**
   * Get the underlying PptxGenJS instance
   * This is needed for components that need direct access
   */
  getPptx(): PptxGenJS {
    return this.pptx;
  }

  /**
   * Get a PptxInstance for components
   * Provides the interface that components expect
   */
  getPptxInstance(): PptxInstance {
    return this.pptxInstance;
  }

  /**
   * Get shapes object for component rendering
   */
  getShapes(): typeof SHAPES {
    return SHAPES;
  }

  /**
   * Write the presentation to a file
   * @param fileName - Output filename
   */
  async writeFile(fileName: string): Promise<void> {
    await this.pptx.writeFile({ fileName });
  }

  /**
   * Write the presentation to a buffer
   * Useful for testing or further processing
   */
  async writeBuffer(): Promise<Uint8Array> {
    const result = await this.pptx.write({ outputType: 'nodebuffer' });
    // Ensure we return Uint8Array
    if (typeof result === 'string') {
      throw new Error('Expected buffer, got string');
    }
    return result as Uint8Array;
  }
}
