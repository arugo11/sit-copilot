/**
 * Components barrel exports
 *
 * Main export point for all poster components.
 * Import from this file for clean access to all components.
 */

// Primitives
export {
  TextComponent,
  createStyledText,
  BoxComponent,
  createSectionBox,
  createDivider,
  ImageComponent,
  createLogo,
} from './primitives/index.js';

export type {
  TextOptions,
  BoxOptions,
  ImageOptions,
  ImageSizing,
} from './primitives/index.js';

// Sections
export {
  BackgroundSection,
  createDefaultBackgroundSection,
  ObjectivesSection,
  createDefaultObjectivesSection,
  AIUsageSection,
  createDefaultAIUsageSection,
  ResultsSection,
  createDefaultResultsSection,
  FuturePlansSection,
  createDefaultFuturePlansSection,
} from './sections/index.js';

export type {
  BackgroundContent,
  ObjectivesContent,
  AIUsageContent,
  ResultsContent,
  MetricItem,
  FuturePlansContent,
} from './sections/index.js';

// Header
export { HeaderComponent, createDefaultHeader } from './header.js';
export type { HeaderContent } from './header.js';
