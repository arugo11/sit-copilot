/**
 * Results Section Component
 *
 * Renders the "4. 成果・出力" section showing KPI metrics and key achievements.
 * Spans 8 columns (columns 0-7) starting below the AI Usage section.
 */

import type { Box, Component, Slide } from '../../domain/types.js';
import { colX, colWidth } from '../../layout/grid.js';
import { COLORS } from '../../theme/colors.js';
import { FONTS } from '../../theme/typography.js';
import { TEXT_STYLES } from '../../theme/typography.js';
import { TextComponent, BoxComponent } from '../primitives/index.js';

/**
 * Metric display item
 */
export interface MetricItem {
  name: string;
  value: string;
  color?: string;
}

/**
 * Content for the Results section
 */
export interface ResultsContent {
  /** Performance metrics */
  metrics: MetricItem[];
  /** Key achievement highlights */
  highlights: string[];
  /** Prompt design highlights */
  promptHighlights: string[];
}

/**
 * PptxGenJS instance interface
 */
interface PptxInstance {
  shapes: { RECTANGLE: string };
}

/**
 * Results section component
 */
export class ResultsSection implements Component {
  private readonly pptx: PptxInstance;
  private readonly content: ResultsContent;
  private readonly startY: number;
  private readonly height: number;

  constructor(
    pptx: PptxInstance,
    content: ResultsContent,
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
      x: colX(0),
      y: this.startY,
      w: colWidth(8),
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
      text: '4. 成果・出力',
      ...TEXT_STYLES.sectionHeader,
    });
    header.render(
      { x: box.x + 0.2, y: box.y + 0.2, w: box.w - 0.4, h: 1 },
      slide,
    );

    // Model Performance subsection
    this.renderPerformanceMetrics(box, slide);

    // Key Achievements subsection
    this.renderAchievements(box, slide);

    // Prompt Design highlights
    this.renderPromptDesign(box, slide);
  }

  /**
   * Render performance metrics grid
   */
  private renderPerformanceMetrics(box: Box, slide: Slide): void {
    const metricsY = box.y + 1.3;
    const metricsPerRow = 3;
    const metricW = (box.w - 0.6) / metricsPerRow;
    const metricH = 1.4;

    this.content.metrics.forEach((metric, i) => {
      const row = Math.floor(i / metricsPerRow);
      const col = i % metricsPerRow;

      const metricBox = new BoxComponent(this.pptx, {
        fill: metric.color || COLORS.secondary,
        border: { color: COLORS.primary, width: 1 },
      });
      metricBox.render(
        {
          x: box.x + 0.2 + col * (metricW + 0.1),
          y: metricsY + row * (metricH + 0.3),
          w: metricW,
          h: metricH,
        },
        slide,
      );

      const metricName = new TextComponent(this.pptx, {
        text: metric.name,
        fontSize: FONTS.body,
        color: COLORS.white,
        bold: false,
        align: 'center',
      });
      metricName.render(
        {
          x: box.x + 0.2 + col * (metricW + 0.1),
          y: metricsY + row * (metricH + 0.3) + 0.15,
          w: metricW,
          h: 0.45,
        },
        slide,
      );

      const metricValue = new TextComponent(this.pptx, {
        text: metric.value,
        fontSize: FONTS.section,
        color: COLORS.white,
        bold: true,
        align: 'center',
        valign: 'middle',
      });
      metricValue.render(
        {
          x: box.x + 0.2 + col * (metricW + 0.1),
          y: metricsY + row * (metricH + 0.3) + 0.55,
          w: metricW,
          h: 0.8,
        },
        slide,
      );
    });
  }

  /**
   * Render key achievements
   */
  private renderAchievements(box: Box, slide: Slide): void {
    const achievementsY = box.y + 4.2;

    const achievementsHeader = new TextComponent(this.pptx, {
      text: '主要成果',
      fontSize: FONTS.subsection,
      color: COLORS.primary,
      bold: true,
    });
    achievementsHeader.render(
      { x: box.x + 0.2, y: achievementsY, w: box.w - 0.4, h: 0.5 },
      slide,
    );

    const achievementsText = new TextComponent(this.pptx, {
      text: this.content.highlights.map((h) => `• ${h}`),
      fontSize: FONTS.body,
      color: COLORS.text,
      lineSpacing: 1.3,
    });
    achievementsText.render(
      { x: box.x + 0.2, y: achievementsY + 0.6, w: box.w - 0.4, h: 2.5 },
      slide,
    );
  }

  /**
   * Render prompt design highlights
   */
  private renderPromptDesign(box: Box, slide: Slide): void {
    const promptY = box.y + 7;

    const promptHeader = new TextComponent(this.pptx, {
      text: 'プロンプト設計のイノベーション',
      fontSize: FONTS.subsection,
      color: COLORS.accent,
      bold: true,
    });
    promptHeader.render(
      { x: box.x + 0.2, y: promptY, w: box.w - 0.4, h: 0.5 },
      slide,
    );

    const promptText = new TextComponent(this.pptx, {
      text: this.content.promptHighlights.map((p) => `• ${p}`),
      fontSize: FONTS.body,
      color: COLORS.text,
      lineSpacing: 1.3,
    });
    promptText.render(
      { x: box.x + 0.2, y: promptY + 0.6, w: box.w - 0.4, h: 2 },
      slide,
    );
  }
}

/**
 * Create a results section with default content
 */
export function createDefaultResultsSection(pptx: PptxInstance): ResultsSection {
  const defaultContent: ResultsContent = {
    metrics: [
      { name: 'ASR精度', value: '87%', color: '#14B8A6' },
      { name: 'QA関連性', value: '92%', color: '#6366F1' },
      { name: '字幕遅延', value: '2.8s', color: '#3B82F6' },
      { name: 'QA遅延', value: '4.2s', color: '#8B5CF6' },
      { name: 'Citation精度', value: '96%', color: '#EC4899' },
    ],
    highlights: [
      'source-only設計による根拠のない回答の排除',
      'Verifierによるハルシネーション抑制',
      'アクセシビリティ対応（文字サイズ・高コントラスト・やさしい日本語）',
    ],
    promptHighlights: [
      '動的コンテキストウィンドウ（要約: 直近60秒）',
      '根拠不足時のフォールバック機構',
      '3言語リアルタイム切替',
    ],
  };
  return new ResultsSection(pptx, defaultContent);
}
