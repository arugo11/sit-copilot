/**
 * Sections barrel exports
 *
 * Exports all section components for poster rendering.
 */

export { BackgroundSection, createDefaultBackgroundSection } from './background.js';
export type { BackgroundContent } from './background.js';

export { ObjectivesSection, createDefaultObjectivesSection } from './objectives.js';
export type { ObjectivesContent } from './objectives.js';

export { AIUsageSection, createDefaultAIUsageSection } from './ai-usage.js';
export type { AIUsageContent } from './ai-usage.js';

export { ResultsSection, createDefaultResultsSection } from './results.js';
export type { ResultsContent, MetricItem } from './results.js';

export {
  FuturePlansSection,
  createDefaultFuturePlansSection,
} from './future-plans.js';
export type { FuturePlansContent } from './future-plans.js';
