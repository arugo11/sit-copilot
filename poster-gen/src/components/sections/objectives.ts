/**
 * Objectives Section Component
 *
 * Renders the "2. 目的・特徴" section showing core features and technical objectives.
 * Spans 7 columns (columns 5-11) starting below the header.
 */

import type { Box, Component, Slide } from '../../domain/types.js';
import { colX, colWidth } from '../../layout/grid.js';
import { COLORS } from '../../theme/colors.js';
import { FONTS } from '../../theme/typography.js';
import { TEXT_STYLES } from '../../theme/typography.js';
import { TextComponent, BoxComponent } from '../primitives/index.js';

/**
 * Content for the Objectives section
 */
export interface ObjectivesContent {
  /** Core features list */
  features: string[];
  /** Technical objectives with metrics */
  technical: {
    target: string;
    metric: string;
  }[];
}

/**
 * PptxGenJS instance interface
 */
interface PptxInstance {
  shapes: { RECTANGLE: string };
}

/**
 * Objectives section component
 */
export class ObjectivesSection implements Component {
  private readonly pptx: PptxInstance;
  private readonly content: ObjectivesContent;
  private readonly startY: number;
  private readonly height: number;

  constructor(
    pptx: PptxInstance,
    content: ObjectivesContent,
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
      x: colX(5),
      y: this.startY,
      w: colWidth(7),
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
      text: '2. 目的・特徴',
      ...TEXT_STYLES.sectionHeader,
    });
    header.render(
      { x: box.x + 0.2, y: box.y + 0.2, w: box.w - 0.4, h: 1 },
      slide,
    );

    // Core features subsection
    const featuresHeader = new TextComponent(this.pptx, {
      text: 'コア機能',
      fontSize: FONTS.subsection,
      color: COLORS.primary,
      bold: true,
    });
    featuresHeader.render(
      { x: box.x + 0.2, y: box.y + 1.2, w: box.w - 0.4, h: 0.5 },
      slide,
    );

    const featuresText = new TextComponent(this.pptx, {
      text: this.content.features,
      fontSize: FONTS.body,
      color: COLORS.text,
      lineSpacing: 1.4,
    });
    featuresText.render(
      { x: box.x + 0.2, y: box.y + 1.8, w: box.w - 0.4, h: 3 },
      slide,
    );

    // Technical objectives subsection
    const techHeader = new TextComponent(this.pptx, {
      text: '技術目標',
      fontSize: FONTS.subsection,
      color: COLORS.primary,
      bold: true,
    });
    techHeader.render(
      { x: box.x + 0.2, y: box.y + 5, w: box.w - 0.4, h: 0.5 },
      slide,
    );

    // Technical metrics displayed horizontally
    const metricBoxWidth = (box.w - 0.4) / this.content.technical.length;
    this.content.technical.forEach((tech, i) => {
      const metricBg = new BoxComponent(this.pptx, {
        fill: COLORS.secondary,
        border: undefined,
      });
      metricBg.render(
        {
          x: box.x + 0.2 + i * metricBoxWidth + 0.1,
          y: box.y + 5.6,
          w: metricBoxWidth - 0.2,
          h: 1.8,
        },
        slide,
      );

      const metricLabel = new TextComponent(this.pptx, {
        text: tech.target,
        fontSize: FONTS.caption,
        color: COLORS.white,
        bold: false,
      });
      metricLabel.render(
        {
          x: box.x + 0.2 + i * metricBoxWidth + 0.1,
          y: box.y + 5.7,
          w: metricBoxWidth - 0.2,
          h: 0.4,
        },
        slide,
      );

      const metricValue = new TextComponent(this.pptx, {
        text: tech.metric,
        fontSize: FONTS.subsection,
        color: COLORS.white,
        bold: true,
        align: 'center',
      });
      metricValue.render(
        {
          x: box.x + 0.2 + i * metricBoxWidth + 0.1,
          y: box.y + 6.2,
          w: metricBoxWidth - 0.2,
          h: 1,
        },
        slide,
      );
    });
  }
}

/**
 * Create an objectives section with default content
 */
export function createDefaultObjectivesSection(
  pptx: PptxInstance,
): ObjectivesSection {
  const defaultContent: ObjectivesContent = {
    features: [
      'リアルタイム字幕生成（音声認識+補正）',
      '講義スライドを活用した文脈理解Q&A',
      '情報源の明示によるハルシネーション抑制',
      'マルチモーダル入力（音声・スライド画像・テキスト）',
      'アクセシビリティ機能（文字サイズ調整・ハイコントラスト）',
    ],
    technical: [
      { target: '字幕生成', metric: '< 3秒' },
      { target: 'Q&A応答', metric: '< 5秒' },
      { target: 'ASR精度', metric: '> 85%' },
      { target: 'Q&A関連度', metric: '> 90%' },
    ],
  };
  return new ObjectivesSection(pptx, defaultContent);
}
