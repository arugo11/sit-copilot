/**
 * Header Component
 *
 * Renders the poster header with title, subtitle, authors, affiliation, and logos.
 * Spans the full width of the A0 poster with a height of ~170mm (6.7 inches).
 */

import type { Box, Component, Slide } from '../domain/types.js';
import { A0_WIDTH, mmToInches } from '../layout/a0.js';
import { COLORS } from '../theme/colors.js';
import { FONTS, FONT_FAMILIES } from '../theme/typography.js';
import { TextComponent, BoxComponent, ImageComponent } from './primitives/index.js';

/**
 * Header content definition
 */
export interface HeaderContent {
  /** Main poster title */
  title: string;
  /** Subtitle below title */
  subtitle: string;
  /** Author names (will be joined with commas) */
  authors: string[];
  /** Institution/affiliation */
  affiliation: string;
  /** Optional event/competition name */
  event?: string;
  /** Optional logo path (top right) */
  logoPath?: string;
  /** Optional secondary logo path (bottom right) */
  logoPath2?: string;
}

/**
 * PptxGenJS instance interface
 */
interface PptxInstance {
  shapes: { RECTANGLE: string; LINE?: string };
}

/**
 * Header component
 */
export class HeaderComponent implements Component {
  private readonly pptx: PptxInstance;
  private readonly content: HeaderContent;
  private readonly height: number;
  private readonly margin: number;

  constructor(
    pptx: PptxInstance,
    content: HeaderContent,
    height?: number,
    margin?: number,
  ) {
    this.pptx = pptx;
    this.content = content;
    this.height = height || mmToInches(170); // Default 170mm
    this.margin = margin || 1; // Default 1 inch margins
  }

  measure(): Box {
    return {
      x: 0,
      y: 0,
      w: A0_WIDTH,
      h: this.height,
    };
  }

  render(box: Box, slide: Slide): void {
    // Header background
    const bg = new BoxComponent(this.pptx, {
      fill: COLORS.white,
      border: undefined,
    });
    bg.render(box, slide);

    const contentW = box.w - this.margin * 2;

    // Title (centered, large)
    const title = new TextComponent(this.pptx, {
      text: this.content.title,
      fontSize: FONTS.title,
      color: COLORS.primary,
      bold: true,
      align: 'center',
      valign: 'middle',
      fontFace: FONT_FAMILIES.primary,
    });
    title.render(
      {
        x: this.margin,
        y: 0.3,
        w: contentW,
        h: 2,
      },
      slide,
    );

    // Subtitle
    const subtitle = new TextComponent(this.pptx, {
      text: this.content.subtitle,
      fontSize: FONTS.subtitle,
      color: COLORS.text,
      bold: false,
      align: 'center',
      valign: 'middle',
      fontFace: FONT_FAMILIES.secondary,
    });
    subtitle.render(
      {
        x: this.margin,
        y: 2.2,
        w: contentW,
        h: 1.2,
      },
      slide,
    );

    // Authors
    const authors = new TextComponent(this.pptx, {
      text: this.content.authors.join(' / '),
      fontSize: FONTS.authors,
      color: COLORS.text,
      bold: false,
      align: 'center',
      valign: 'middle',
      fontFace: FONT_FAMILIES.primary,
    });
    authors.render(
      {
        x: this.margin,
        y: 3.3,
        w: contentW,
        h: 0.8,
      },
      slide,
    );

    // Affiliation
    const affiliation = new TextComponent(this.pptx, {
      text: this.content.affiliation,
      fontSize: FONTS.body,
      color: COLORS.mediumGray,
      bold: false,
      align: 'center',
      valign: 'middle',
      fontFace: FONT_FAMILIES.primary,
    });
    affiliation.render(
      {
        x: this.margin,
        y: 4,
        w: contentW,
        h: 0.6,
      },
      slide,
    );

    // Event/competition name (if provided)
    if (this.content.event) {
      const eventText = new TextComponent(this.pptx, {
        text: this.content.event,
        fontSize: FONTS.caption,
        color: COLORS.accent,
        bold: true,
        align: 'center',
        valign: 'middle',
        fontFace: FONT_FAMILIES.secondary,
      });
      eventText.render(
        {
          x: this.margin,
          y: 4.5,
          w: contentW,
          h: 0.5,
        },
        slide,
      );
    }

    // Primary logo (top right, if provided)
    if (this.content.logoPath) {
      const logo = new ImageComponent(this.pptx, {
        path: this.content.logoPath,
        sizing: 'contain',
      });
      logo.render(
        {
          x: box.w - 2.5,
          y: 0.3,
          w: 2,
          h: 2,
        },
        slide,
      );
    }

    // Secondary logo (if provided)
    if (this.content.logoPath2) {
      const logo2 = new ImageComponent(this.pptx, {
        path: this.content.logoPath2,
        sizing: 'contain',
      });
      logo2.render(
        {
          x: box.w - 2.5,
          y: 2.5,
          w: 2,
          h: 1,
        },
        slide,
      );
    }

    // Divider line
    const divider = new BoxComponent(this.pptx, {
      fill: COLORS.primary,
      border: undefined,
    });
    divider.render(
      {
        x: this.margin,
        y: this.height - 0.1,
        w: box.w - this.margin * 2,
        h: 0.1,
      },
      slide,
    );
  }
}

/**
 * Create a header with default SIT Copilot content
 */
export function createDefaultHeader(
  pptx: PptxInstance,
): HeaderComponent {
  const defaultContent: HeaderContent = {
    title: 'SIT Copilot',
    subtitle: '講義支援AIシステム',
    authors: ['嶋中雄大'],
    affiliation: '芝浦工業大学',
    event: 'AI Innovators Cup @ 芝浦工業大学 2026',
    // logoPath: 'assets/logos/sit-logo.png',
    // logoPath2: 'assets/logos/team-logo.png',
  };
  return new HeaderComponent(pptx, defaultContent);
}
