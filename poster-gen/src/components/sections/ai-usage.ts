/**
 * AI Usage Section Component
 *
 * Renders the "3. AI活用方法" HERO section showing multi-modal integration flow.
 * Spans all 12 columns with central diagram and feature breakdowns.
 */

import type { Box, Component, Slide } from '../../domain/types.js';
import { colX, colWidth } from '../../layout/grid.js';
import { COLORS } from '../../theme/colors.js';
import { FONTS } from '../../theme/typography.js';
import { TEXT_STYLES } from '../../theme/typography.js';
import { TextComponent, BoxComponent } from '../primitives/index.js';

/**
 * Flow diagram node
 */
export interface FlowNode {
  label: string;
  color: string;
  x: number;
  y: number;
}

/**
 * PptxGenJS instance interface
 */
interface PptxInstance {
  shapes: {
    RECTANGLE: string;
    LINE: string;
  };
}

/**
 * Content for the AI Usage section
 */
export interface AIUsageContent {
  /** Flow diagram nodes */
  flows: FlowNode[];
  /** Feature breakdown items */
  features: {
    name: string;
    description: string;
    kpi: string;
  }[];
  /** Prompt examples */
  prompts: {
    name: string;
    content: string;
  }[];
}

/**
 * AI Usage section component
 */
export class AIUsageSection implements Component {
  private readonly pptx: PptxInstance;
  private readonly content: AIUsageContent;
  private readonly startY: number;
  private readonly height: number;

  constructor(
    pptx: PptxInstance,
    content: AIUsageContent,
    startY = 15,
    height = 12,
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
      w: colWidth(12),
      h: this.height,
    };
  }

  render(box: Box, slide: Slide): void {
    // Section background with accent color
    const bg = new BoxComponent(this.pptx, {
      fill: COLORS.lightGray,
      border: { color: COLORS.primary, width: 2 },
    });
    bg.render(box, slide);

    // Section header
    const header = new TextComponent(this.pptx, {
      text: '3. AI活用・応用方法',
      ...TEXT_STYLES.sectionHeader,
    });
    header.render(
      { x: box.x + 0.3, y: box.y + 0.2, w: box.w - 0.6, h: 1 },
      slide,
    );

    // Subtitle for the flow diagram
    const subtitle = new TextComponent(this.pptx, {
      text: 'マルチモーダル統合フロー',
      fontSize: FONTS.subsection,
      color: COLORS.secondary,
      bold: true,
      align: 'center',
    });
    subtitle.render(
      { x: box.x, y: box.y + 1.3, w: box.w, h: 0.6 },
      slide,
    );

    // Render flow diagram
    this.renderFlowDiagram(box, slide);

    // Render feature breakdown boxes
    this.renderFeatureBoxes(box, slide);

    // Render prompt examples
    this.renderPrompts(box, slide);
  }

  /**
   * Render the multi-modal flow diagram
   */
  private renderFlowDiagram(box: Box, slide: Slide): void {
    const diagramY = box.y + 2.2;
    const nodeW = 2.5;
    const nodeH = 0.8;
    const centerX = box.x + box.w / 2;

    // Define flow nodes (multi-modal integration)
    const nodes: FlowNode[] = [
      { label: 'Speech\n🎤', color: '#3B82F6', x: centerX - 10, y: diagramY },
      { label: 'Slide\n📄', color: '#8B5CF6', x: centerX - 5, y: diagramY },
      { label: 'Question\n❓', color: '#EC4899', x: centerX + 2, y: diagramY },
      { label: 'ASR', color: '#14B8A6', x: centerX - 9, y: diagramY + 1.5 },
      { label: 'OCR', color: '#F59E0B', x: centerX - 4, y: diagramY + 1.5 },
      { label: 'AI Search\n🔍', color: '#6366F1', x: centerX - 2, y: diagramY + 2.8 },
      { label: 'GPT-4o\n🤖', color: '#8B5CF6', x: centerX - 2, y: diagramY + 3.8 },
      { label: 'Caption', color: '#10B981', x: centerX - 8, y: diagramY + 4.8 },
      { label: 'Answer', color: '#3B82F6', x: centerX - 1, y: diagramY + 4.8 },
    ];

    // Render nodes
    nodes.forEach((node) => {
      const nodeBg = new BoxComponent(this.pptx, {
        fill: node.color,
        border: { color: COLORS.primary, width: 1 },
      });
      nodeBg.render(
        { x: node.x, y: node.y, w: nodeW, h: nodeH },
        slide,
      );

      const nodeText = new TextComponent(this.pptx, {
        text: node.label,
        fontSize: FONTS.caption,
        color: COLORS.white,
        bold: true,
        align: 'center',
        valign: 'middle',
      });
      nodeText.render(
        { x: node.x, y: node.y, w: nodeW, h: nodeH },
        slide,
      );
    });

    // Add flow arrows (using line shapes)
    this.addArrow(slide, centerX - 8.5, diagramY + 0.8, centerX - 8.5, diagramY + 1.4);
    this.addArrow(slide, centerX - 3.5, diagramY + 0.8, centerX - 3.5, diagramY + 1.4);
    this.addArrow(slide, centerX - 8.5, diagramY + 2.4, centerX - 2, diagramY + 2.7);
    this.addArrow(slide, centerX - 3.5, diagramY + 2.4, centerX - 2, diagramY + 2.7);
    this.addArrow(slide, centerX + 0.5, diagramY + 0.8, centerX - 0.5, diagramY + 3.7);
    this.addArrow(slide, centerX - 2, diagramY + 3.7, centerX - 7, diagramY + 4.7);
    this.addArrow(slide, centerX - 2, diagramY + 3.7, centerX, diagramY + 4.7);
  }

  /**
   * Add an arrow between two points
   */
  private addArrow(
    slide: Slide,
    x1: number,
    y1: number,
    x2: number,
    y2: number,
  ): void {
    slide.addShape(this.pptx.shapes.LINE, {
      x: x1,
      y: y1,
      w: x2 - x1,
      h: y2 - y1,
      line: { color: COLORS.primary.slice(1), width: 2, endArrowType: 'triangle' },
    });
  }

  /**
   * Render feature breakdown boxes
   */
  private renderFeatureBoxes(box: Box, slide: Slide): void {
    const boxY = box.y + 7.5;
    const boxH = 2.5;
    const boxW = (box.w - 0.6) / 3;
    const gap = 0.2;

    this.content.features.slice(0, 3).forEach((feature, i) => {
      const featureBox = new BoxComponent(this.pptx, {
        fill: COLORS.white,
        border: { color: COLORS.secondary, width: 1 },
      });
      featureBox.render(
        {
          x: box.x + 0.2 + i * (boxW + gap),
          y: boxY,
          w: boxW,
          h: boxH,
        },
        slide,
      );

      const title = new TextComponent(this.pptx, {
        text: feature.name,
        fontSize: FONTS.body,
        color: COLORS.primary,
        bold: true,
      });
      title.render(
        {
          x: box.x + 0.3 + i * (boxW + gap),
          y: boxY + 0.2,
          w: boxW - 0.2,
          h: 0.5,
        },
        slide,
      );

      const desc = new TextComponent(this.pptx, {
        text: feature.description,
        fontSize: FONTS.caption,
        color: COLORS.text,
      });
      desc.render(
        {
          x: box.x + 0.3 + i * (boxW + gap),
          y: boxY + 0.8,
          w: boxW - 0.2,
          h: 1.2,
        },
        slide,
      );

      const kpi = new TextComponent(this.pptx, {
        text: `KPI: ${feature.kpi}`,
        fontSize: FONTS.caption,
        color: COLORS.accent,
        bold: true,
      });
      kpi.render(
        {
          x: box.x + 0.3 + i * (boxW + gap),
          y: boxY + 2,
          w: boxW - 0.2,
          h: 0.4,
        },
        slide,
      );
    });
  }

  /**
   * Render prompt examples
   */
  private renderPrompts(box: Box, slide: Slide): void {
    const promptY = box.y + 10.3;
    const promptH = 1.5;

    const promptBox = new BoxComponent(this.pptx, {
      fill: '#FEEBC8',
      border: { color: COLORS.accent.slice(1), width: 1 },
    });
    promptBox.render(
      { x: box.x + 0.2, y: promptY, w: box.w - 0.4, h: promptH },
      slide,
    );

    const promptLabel = new TextComponent(this.pptx, {
      text: 'プロンプト設計例',
      fontSize: FONTS.caption,
      color: COLORS.primary,
      bold: true,
    });
    promptLabel.render(
      { x: box.x + 0.3, y: promptY + 0.1, w: 3, h: 0.4 },
      slide,
    );

    const promptText = new TextComponent(this.pptx, {
      text: this.content.prompts.map((p) => `【${p.name}】${p.content}`).join('\n'),
      fontSize: FONTS.small,
      color: COLORS.text,
    });
    promptText.render(
      { x: box.x + 0.3, y: promptY + 0.5, w: box.w - 0.6, h: promptH - 0.6 },
      slide,
    );
  }
}

/**
 * Create an AI usage section with default content
 */
export function createDefaultAIUsageSection(pptx: PptxInstance): AIUsageSection {
  const defaultContent: AIUsageContent = {
    flows: [],
    features: [
      {
        name: '字幕生成フロー',
        description: 'リアルタイムASR・補正・ソースタグ付け',
        kpi: '2.8秒 / 87%',
      },
      {
        name: 'Q&Aフロー',
        description: '文脈理解・情報源検証・引用表示',
        kpi: '4.2秒 / 92%',
      },
      {
        name: 'OCRフロー',
        description: 'スライド抽出・ROI対応・品質フィルタ',
        kpi: '94%成功率',
      },
    ],
    prompts: [
      {
        name: '字幕',
        content: '直近60秒の講義内容を要約。関連ポイントをグループ化。ソースを明記: [音声][スライド][板書]',
      },
      {
        name: 'Q&A',
        content: '提供された講義記録とスライドテキストのみを使用して質問に答える。(chunk_id)でソースを引用',
      },
    ],
  };
  return new AIUsageSection(pptx, defaultContent);
}
