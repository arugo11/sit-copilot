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
   * Render the dual-flow diagram (Captioning flow + QA flow)
   */
  private renderFlowDiagram(box: Box, slide: Slide): void {
    const diagramY = box.y + 2.2;
    const nodeW = 3.0;
    const nodeH = 0.9;

    // === Left flow: Captioning (columns 0-5) ===
    const leftX = box.x + 1.5;

    // Flow label
    const captionFlowLabel = new TextComponent(this.pptx, {
      text: '[ 字幕生成フロー ]',
      fontSize: FONTS.caption,
      color: COLORS.secondary,
      bold: true,
      align: 'center',
    });
    captionFlowLabel.render(
      { x: leftX - 0.5, y: diagramY - 0.5, w: nodeW + 1, h: 0.4 },
      slide,
    );

    const captionNodes: FlowNode[] = [
      { label: '音声入力',         color: '#3B82F6', x: leftX, y: diagramY },
      { label: '音声認識 (ASR)',    color: '#14B8A6', x: leftX, y: diagramY + 1.4 },
      { label: '日本語補正',        color: '#6366F1', x: leftX, y: diagramY + 2.8 },
      { label: '字幕・要約',        color: '#10B981', x: leftX, y: diagramY + 4.2 },
    ];

    // === Right flow: QA (columns 6-11) ===
    const rightX = box.x + box.w - nodeW - 1.5;

    const qaFlowLabel = new TextComponent(this.pptx, {
      text: '[ Q&A フロー ]',
      fontSize: FONTS.caption,
      color: '#EC4899',
      bold: true,
      align: 'center',
    });
    qaFlowLabel.render(
      { x: rightX - 0.5, y: diagramY - 0.5, w: nodeW + 1, h: 0.4 },
      slide,
    );

    const qaNodes: FlowNode[] = [
      { label: '質問入力',           color: '#EC4899', x: rightX, y: diagramY },
      { label: 'ハイブリッド検索',    color: '#6366F1', x: rightX, y: diagramY + 1.4 },
      { label: 'GPT-4o',            color: '#8B5CF6', x: rightX, y: diagramY + 2.8 },
      { label: '根拠付き回答',       color: '#3B82F6', x: rightX, y: diagramY + 4.2 },
    ];

    // Render all nodes
    [...captionNodes, ...qaNodes].forEach((node) => {
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

    // Caption flow arrows (vertical)
    const lMid = leftX + nodeW / 2;
    this.addArrow(slide, lMid, diagramY + nodeH, lMid, diagramY + 1.4);
    this.addArrow(slide, lMid, diagramY + 1.4 + nodeH, lMid, diagramY + 2.8);
    this.addArrow(slide, lMid, diagramY + 2.8 + nodeH, lMid, diagramY + 4.2);

    // QA flow arrows (vertical)
    const rMid = rightX + nodeW / 2;
    this.addArrow(slide, rMid, diagramY + nodeH, rMid, diagramY + 1.4);
    this.addArrow(slide, rMid, diagramY + 1.4 + nodeH, rMid, diagramY + 2.8);
    this.addArrow(slide, rMid, diagramY + 2.8 + nodeH, rMid, diagramY + 4.2);

    // Cross-flow arrow: Caption transcript feeds into QA search
    this.addArrow(slide, leftX + nodeW, diagramY + 2.8 + nodeH / 2, rightX, diagramY + 1.4 + nodeH / 2);

    // Cross-flow label
    const crossLabel = new TextComponent(this.pptx, {
      text: '講義記録を検索対象として利用',
      fontSize: FONTS.small,
      color: COLORS.mediumGray,
      align: 'center',
    });
    crossLabel.render(
      {
        x: leftX + nodeW + 0.2,
        y: diagramY + 1.8,
        w: rightX - leftX - nodeW - 0.4,
        h: 0.4,
      },
      slide,
    );
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
   * Render feature breakdown boxes (2 features side by side)
   */
  private renderFeatureBoxes(box: Box, slide: Slide): void {
    const boxY = box.y + 7.5;
    const boxH = 2.5;
    const featureCount = Math.min(this.content.features.length, 2);
    const boxW = (box.w - 0.6) / featureCount;
    const gap = 0.2;

    this.content.features.slice(0, featureCount).forEach((feature, i) => {
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
        text: feature.kpi,
        fontSize: FONTS.body,
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
        description: 'リアルタイムASR・日本語補正・30秒ローリング要約',
        kpi: '遅延 2.8秒 / 精度 87%',
      },
      {
        name: 'Q&Aフロー',
        description: 'ハイブリッド検索・source-only回答・Verifier検証',
        kpi: '遅延 4.2秒 / 関連性 92%',
      },
    ],
    prompts: [
      {
        name: '要約',
        content: '直近60秒の講義内容を要約。関連ポイントをグループ化。最大150語。',
      },
      {
        name: 'Q&A',
        content: '講義記録のみを使用して質問に回答。(chunk_id)でソースを引用。根拠不足時は「講義内では確認できない」と回答。',
      },
    ],
  };
  return new AIUsageSection(pptx, defaultContent);
}
