/**
 * Poster Renderer
 *
 * Main orchestrator for rendering all poster components.
 * Coordinates the layout and rendering of all sections.
 */

import { PptxAdapter } from './pptx-adapter.js';
import type { PosterContent } from '../domain/types.js';
import { HeaderComponent } from '../components/header.js';
import { BackgroundSection } from '../components/sections/background.js';
import { ObjectivesSection } from '../components/sections/objectives.js';
import { AIUsageSection, type AIUsageContent, type FlowNode } from '../components/sections/ai-usage.js';
import { ResultsSection } from '../components/sections/results.js';
import { FuturePlansSection } from '../components/sections/future-plans.js';

/**
 * Layout configuration for poster sections
 */
interface LayoutConfig {
  /** Header height in inches */
  headerHeight: number;
  /** Background/Objectives row Y position */
  row1Y: number;
  /** Background/Objectives row height */
  row1Height: number;
  /** AI Usage section Y position */
  row2Y: number;
  /** AI Usage section height */
  row2Height: number;
  /** Results/Future Plans row Y position */
  row3Y: number;
  /** Results/Future Plans row height */
  row3Height: number;
}

/**
 * Default layout configuration matching A0 poster design
 */
const DEFAULT_LAYOUT: LayoutConfig = {
  headerHeight: 5.5,   // ~170mm converted to inches
  row1Y: 6.5,          // Background/Objectives start
  row1Height: 8,       // Background/Objectives height
  row2Y: 15,           // AI Usage start
  row2Height: 12,      // AI Usage height
  row3Y: 27.5,         // Results/Future Plans start
  row3Height: 10,      // Results/Future Plans height
};

/**
 * Poster content adapter interfaces
 * These map the JSON content to component-specific formats
 */
interface HeaderContent {
  title: string;
  subtitle: string;
  authors: string[];
  affiliation: string;
  event?: string;
}

interface BackgroundContent {
  problems: string[];
  audience: string[];
}

interface ObjectivesContent {
  features: string[];
  technical: { target: string; metric: string }[];
}

interface ResultsContent {
  metrics: {
    name: string;
    value: string;
    color?: string;
  }[];
  highlights: string[];
  promptHighlights: string[];
}

interface FuturePlansContent {
  shortTerm: string[];
  longTerm: string[];
  qrCodePath?: string;
}

/**
 * Poster renderer class
 */
export class PosterRenderer {
  private readonly adapter: PptxAdapter;
  private readonly layout: LayoutConfig;

  constructor(layout?: Partial<LayoutConfig>) {
    this.adapter = new PptxAdapter();
    this.layout = { ...DEFAULT_LAYOUT, ...layout };
  }

  /**
   * Render the complete poster
   * @param content - Poster content from JSON
   * @param outputPath - Optional output filename
   */
  async render(content: PosterContent, outputPath = 'sit-copilot-poster.pptx'): Promise<void> {
    console.log('Creating poster slide...');
    const slide = this.adapter.createSlide();
    const pptx = this.adapter.getPptxInstance();

    // Render header
    console.log('Rendering header...');
    const headerContent: HeaderContent = {
      title: content.meta.title,
      subtitle: content.meta.subtitle,
      authors: content.meta.authors,
      affiliation: content.meta.affiliation,
      event: 'AI Innovators Cup @ Shibaura 2026',
    };
    const header = new HeaderComponent(pptx, headerContent, this.layout.headerHeight);
    header.render({ x: 0, y: 0, w: 33.1, h: this.layout.headerHeight }, slide);

    // Extract sections
    const sections = content.sections as any;

    // Render Background section (columns 0-4, 5 columns)
    console.log('Rendering background section...');
    const backgroundContent: BackgroundContent = sections.background || {
      problems: sections.background?.problems || [],
      audience: sections.background?.audience || [],
    };
    const background = new BackgroundSection(pptx, backgroundContent, this.layout.row1Y, this.layout.row1Height);
    background.render(background.measure(), slide);

    // Render Objectives section (columns 5-11, 7 columns)
    console.log('Rendering objectives section...');
    const objectivesContent: ObjectivesContent = sections.objectives || {
      features: sections.objectives?.features || [],
      technical: sections.objectives?.technical || [],
    };
    const objectives = new ObjectivesSection(pptx, objectivesContent, this.layout.row1Y, this.layout.row1Height);
    objectives.render(objectives.measure(), slide);

    // Render AI Usage section (all 12 columns - HERO)
    console.log('Rendering AI usage section...');
    const aiUsageContent: AIUsageContent = {
      flows: [] as FlowNode[],  // Flow nodes are rendered internally by the component
      features: sections.aiUsage?.flows || sections.aiUsage?.features || [],
      prompts: sections.aiUsage?.prompts || [],
    };
    const aiUsage = new AIUsageSection(pptx, aiUsageContent, this.layout.row2Y, this.layout.row2Height);
    aiUsage.render(aiUsage.measure(), slide);

    // Render Results section (columns 0-7, 8 columns)
    console.log('Rendering results section...');
    const resultsContent: ResultsContent = sections.results || {
      metrics: sections.results?.metrics || [],
      highlights: sections.results?.highlights || [],
      promptHighlights: sections.results?.promptHighlights || [],
    };
    const results = new ResultsSection(pptx, resultsContent, this.layout.row3Y, this.layout.row3Height);
    results.render(results.measure(), slide);

    // Render Future Plans section (columns 8-11, 4 columns)
    console.log('Rendering future plans section...');
    const futurePlansContent: FuturePlansContent = {
      shortTerm: sections.futurePlans?.shortTerm || sections.futurePlans?.slice(0, 3) || [],
      longTerm: sections.futurePlans?.longTerm || sections.futurePlans?.slice(3) || [],
      qrCodePath: (content as any).demoVideoUrl ? undefined : undefined, // QR code path if generated
    };
    const futurePlans = new FuturePlansSection(pptx, futurePlansContent, this.layout.row3Y, this.layout.row3Height);
    futurePlans.render(futurePlans.measure(), slide);

    // Write file
    console.log(`Writing poster to: ${outputPath}`);
    await this.adapter.writeFile(outputPath);
    console.log(`✅ Poster generated successfully: ${outputPath}`);
  }

  /**
   * Get the adapter for advanced operations
   */
  getAdapter(): PptxAdapter {
    return this.adapter;
  }
}
