/**
 * Domain module barrel exports
 *
 * Exports all types, schemas, and validation functions
 * for poster content definition.
 */

// Types
export type {
  Box,
  Component,
  Alignment,
  Spacing,
  ThemeVariant,
  PosterMeta,
  PosterSections,
  PosterContent,
  AIFlowItem,
  PromptExample,
  MetricItem,
} from './types.js';

// Type constants
export { DEFAULT_SPACING } from './types.js';

// Schemas
export {
  posterContentSchema,
  posterMetaSchema,
  posterSectionsSchema,
  aiFlowItemSchema,
  promptExampleSchema,
  metricItemSchema,
  themeVariantSchema,
} from './schema.js';

// Validation functions
export {
  validatePosterContent,
  parsePosterContent,
} from './schema.js';

// Type inference from schemas
export type {
  PosterContent as SchemaPosterContent,
  PosterMeta as SchemaPosterMeta,
  PosterSections as SchemaPosterSections,
  AIFlowItem as SchemaAIFlowItem,
  PromptExample as SchemaPromptExample,
  MetricItem as SchemaMetricItem,
  ThemeVariant as SchemaThemeVariant,
} from './schema.js';
