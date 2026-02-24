/**
 * Background Section Component
 *
 * Renders the "1. 背景" section showing problem statement and target audience.
 * Spans 5 columns (columns 0-4) starting below the header.
 */

import type { Box, Component, Slide } from '../../domain/types.js';
import { colX, colWidth } from '../../layout/grid.js';
import { COLORS } from '../../theme/colors.js';
import { FONTS } from '../../theme/typography.js';
import { TEXT_STYLES } from '../../theme/typography.js';
import { TextComponent, BoxComponent } from '../primitives/index.js';

/**
 * Content for the Background section
 */
export interface BackgroundContent {
  /** Problem statement bullet points */
  problems: string[];
  /** Target audience bullet points */
  audience: string[];
}

/**
 * PptxGenJS instance interface
 */
interface PptxInstance {
  shapes: { RECTANGLE: string };
}

/**
 * Background section component
 */
export class BackgroundSection implements Component {
  private readonly pptx: PptxInstance;
  private readonly content: BackgroundContent;
  private readonly startY: number;
  private readonly height: number;

  constructor(
    pptx: PptxInstance,
    content: BackgroundContent,
    startY = 6.5,
    height = 8,
  ) {
    this.pptx = pptx;
    this.content = content;
    this.startY = startY;
    this.height = height;
  }

  measure(): Box {
    return {
      x: colX(0),
      y: this.startY,
      w: colWidth(5),
      h: this.height,
    };
  }

  render(box: Box, slide: Slide): void {
    // Section background box
    const bg = new BoxComponent(this.pptx, {
      fill: COLORS.white,
      border: { color: COLORS.border, width: 1 },
    });
    bg.render(box, slide);

    // Section header
    const header = new TextComponent(this.pptx, {
      text: '1. 背景',
      ...TEXT_STYLES.sectionHeader,
    });
    header.render(
      { x: box.x + 0.2, y: box.y + 0.2, w: box.w - 0.4, h: 1 },
      slide,
    );

    // Problem subsection
    const problemHeader = new TextComponent(this.pptx, {
      text: '課題',
      fontSize: FONTS.subsection,
      color: COLORS.primary,
      bold: true,
    });
    problemHeader.render(
      { x: box.x + 0.2, y: box.y + 1.2, w: box.w - 0.4, h: 0.5 },
      slide,
    );

    const problemText = new TextComponent(this.pptx, {
      text: this.content.problems.map((p) => `• ${p}`),
      fontSize: FONTS.subsection,
      color: COLORS.text,
      lineSpacing: 1.6,
    });
    problemText.render(
      { x: box.x + 0.3, y: box.y + 1.8, w: box.w - 0.6, h: 3 },
      slide,
    );

    // Target audience subsection
    const audienceHeader = new TextComponent(this.pptx, {
      text: '対象者',
      fontSize: FONTS.subsection,
      color: COLORS.primary,
      bold: true,
    });
    audienceHeader.render(
      { x: box.x + 0.2, y: box.y + 4.5, w: box.w - 0.4, h: 0.5 },
      slide,
    );

    const audienceText = new TextComponent(this.pptx, {
      text: this.content.audience.map((a) => `• ${a}`),
      fontSize: FONTS.subsection,
      color: COLORS.text,
      lineSpacing: 1.6,
    });
    audienceText.render(
      { x: box.x + 0.3, y: box.y + 5.3, w: box.w - 0.6, h: 2.5 },
      slide,
    );
  }
}

/**
 * Create a background section with default content
 */
export function createDefaultBackgroundSection(
  pptx: PptxInstance,
): BackgroundSection {
  const defaultContent: BackgroundContent = {
    problems: [
      '講義は情報密度が高く、聞き漏らしが発生しやすい',
      '非母語話者はリアルタイムでの理解が困難',
      '既存ツールには講義固有の文脈理解がない',
    ],
    audience: [
      '大学生全般（特に留学生）',
      'アクセシビリティ支援が必要な受講者',
    ],
  };
  return new BackgroundSection(pptx, defaultContent);
}
