/**
 * Future Plans Section Component
 *
 * Renders the "5. 今後の展開" section showing short-term and long-term plans.
 * Spans 4 columns (columns 8-11) starting below the AI Usage section.
 */

import type { Box, Component, Slide } from '../../domain/types.js';
import { colX, colWidth } from '../../layout/grid.js';
import { COLORS } from '../../theme/colors.js';
import { FONTS } from '../../theme/typography.js';
import { TEXT_STYLES } from '../../theme/typography.js';
import { TextComponent, BoxComponent, ImageComponent } from '../primitives/index.js';

/**
 * Content for the Future Plans section
 */
export interface FuturePlansContent {
  /** Short-term plans */
  shortTerm: string[];
  /** Long-term plans */
  longTerm: string[];
  /** Path to QR code image for demo video */
  qrCodePath?: string;
}

/**
 * PptxGenJS instance interface
 */
interface PptxInstance {
  shapes: { RECTANGLE: string };
}

/**
 * Future Plans section component
 */
export class FuturePlansSection implements Component {
  private readonly pptx: PptxInstance;
  private readonly content: FuturePlansContent;
  private readonly startY: number;
  private readonly height: number;

  constructor(
    pptx: PptxInstance,
    content: FuturePlansContent,
    startY = 27.5,
    height = 10,
  ) {
    this.pptx = pptx;
    this.content = content;
    this.startY = startY;
    this.height = height;
  }

  measure(): Box {
    return {
      x: colX(8),
      y: this.startY,
      w: colWidth(4),
      h: this.height,
    };
  }

  render(box: Box, slide: Slide): void {
    // Section background
    const bg = new BoxComponent(this.pptx, {
      fill: COLORS.white,
      border: { color: COLORS.border, width: 1 },
    });
    bg.render(box, slide);

    // Section header
    const header = new TextComponent(this.pptx, {
      text: '5. 今後の展開',
      ...TEXT_STYLES.sectionHeader,
    });
    header.render(
      { x: box.x + 0.2, y: box.y + 0.2, w: box.w - 0.4, h: 1 },
      slide,
    );

    // Short-term plans
    this.renderShortTermPlans(box, slide);

    // Long-term plans
    this.renderLongTermPlans(box, slide);

    // QR code for demo video
    if (this.content.qrCodePath) {
      this.renderQRCode(box, slide);
    }
  }

  /**
   * Render short-term plans
   */
  private renderShortTermPlans(box: Box, slide: Slide): void {
    const shortTermY = box.y + 1.3;

    const shortTermHeader = new TextComponent(this.pptx, {
      text: '短期',
      fontSize: FONTS.subsection,
      color: COLORS.secondary,
      bold: true,
    });
    shortTermHeader.render(
      { x: box.x + 0.2, y: shortTermY, w: box.w - 0.4, h: 0.5 },
      slide,
    );

    const shortTermText = new TextComponent(this.pptx, {
      text: this.content.shortTerm.map((p) => `• ${p}`),
      fontSize: FONTS.body,
      color: COLORS.text,
      lineSpacing: 1.3,
    });
    shortTermText.render(
      { x: box.x + 0.2, y: shortTermY + 0.6, w: box.w - 0.4, h: 2.5 },
      slide,
    );
  }

  /**
   * Render long-term plans
   */
  private renderLongTermPlans(box: Box, slide: Slide): void {
    const longTermY = box.y + 4.5;

    const longTermHeader = new TextComponent(this.pptx, {
      text: '長期',
      fontSize: FONTS.subsection,
      color: COLORS.secondary2,
      bold: true,
    });
    longTermHeader.render(
      { x: box.x + 0.2, y: longTermY, w: box.w - 0.4, h: 0.5 },
      slide,
    );

    const longTermText = new TextComponent(this.pptx, {
      text: this.content.longTerm.map((p) => `• ${p}`),
      fontSize: FONTS.body,
      color: COLORS.text,
      lineSpacing: 1.3,
    });
    longTermText.render(
      { x: box.x + 0.2, y: longTermY + 0.6, w: box.w - 0.4, h: 2 },
      slide,
    );
  }

  /**
   * Render QR code for demo video
   */
  private renderQRCode(box: Box, slide: Slide): void {
    const qrY = box.y + 7;
    const qrSize = 2.5;

    const qrBg = new BoxComponent(this.pptx, {
      fill: COLORS.white,
      border: { color: COLORS.primary, width: 2 },
    });
    qrBg.render(
      {
        x: box.x + (box.w - qrSize) / 2,
        y: qrY,
        w: qrSize,
        h: qrSize,
      },
      slide,
    );

    if (this.content.qrCodePath) {
      const qr = new ImageComponent(this.pptx, {
        path: this.content.qrCodePath,
        sizing: 'contain',
      });
      qr.render(
        {
          x: box.x + (box.w - qrSize) / 2 + 0.1,
          y: qrY + 0.1,
          w: qrSize - 0.2,
          h: qrSize - 0.2,
        },
        slide,
      );
    } else {
      // Placeholder QR code text
      const placeholder = new TextComponent(this.pptx, {
        text: 'QR Code',
        fontSize: FONTS.caption,
        color: COLORS.mediumGray,
        align: 'center',
        valign: 'middle',
      });
      placeholder.render(
        {
          x: box.x + (box.w - qrSize) / 2,
          y: qrY,
          w: qrSize,
          h: qrSize,
        },
        slide,
      );
    }

    const qrLabel = new TextComponent(this.pptx, {
      text: 'デモ動画',
      fontSize: FONTS.body,
      color: COLORS.primary,
      bold: true,
      align: 'center',
    });
    qrLabel.render(
      { x: box.x, y: qrY + qrSize + 0.2, w: box.w, h: 0.5 },
      slide,
    );

    const qrSublabel = new TextComponent(this.pptx, {
      text: 'スキャンして3分デモを見る',
      fontSize: FONTS.caption,
      color: COLORS.text,
      align: 'center',
    });
    qrSublabel.render(
      { x: box.x, y: qrY + qrSize + 0.7, w: box.w, h: 0.4 },
      slide,
    );
  }
}

/**
 * Create a future plans section with default content
 */
export function createDefaultFuturePlansSection(
  pptx: PptxInstance,
): FuturePlansSection {
  const defaultContent: FuturePlansContent = {
    shortTerm: [
      '高度なNLP機能（キーワード抽出）',
      '多言語対応（英語・中国語）',
      '使用分析ダッシュボード',
    ],
    longTerm: [
      'LMSプラットフォーム連携',
      '学生用モバイルアプリ',
      'ローカルモデルによるオフラインモード',
    ],
    // qrCodePath: 'assets/images/demo-qr.png', // Optional
  };
  return new FuturePlansSection(pptx, defaultContent);
}
