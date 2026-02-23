/**
 * Zod schemas for poster content validation
 */

import { z } from 'zod';

/**
 * Theme variant enum
 */
export const themeVariantSchema = z.enum(['technical-blue', 'minimal', 'academic']);

/**
 * Poster metadata schema
 */
export const posterMetaSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  subtitle: z.string().min(1, 'Subtitle is required'),
  authors: z.array(z.string()).min(1, 'At least one author is required'),
  affiliation: z.string().min(1, 'Affiliation is required'),
  date: z.string().min(1, 'Date is required'),
});

/**
 * Background section schema
 */
export const backgroundSectionSchema = z.object({
  problems: z.array(z.string()).min(1, 'At least one problem is required'),
  audience: z.array(z.string()).min(1, 'At least one audience item is required'),
});

/**
 * Objectives section schema
 */
export const objectivesSectionSchema = z.object({
  features: z.array(z.string()).min(1, 'At least one feature is required'),
  technical: z.array(z.object({
    target: z.string(),
    metric: z.string(),
  })).min(1, 'At least one technical objective is required'),
});

/**
 * AI Flow item schema (used in features for aiUsage)
 */
export const aiFlowItemSchema = z.object({
  name: z.string().min(1, 'Flow name is required'),
  description: z.string().min(1, 'Flow description is required'),
  kpi: z.string().min(1, 'KPI is required'),
});

/**
 * Prompt example schema
 */
export const promptExampleSchema = z.object({
  name: z.string().min(1, 'Prompt name is required'),
  content: z.string().min(1, 'Prompt content is required'),
});

/**
 * AI Usage section schema
 */
export const aiUsageSectionSchema = z.object({
  features: z.array(aiFlowItemSchema).min(1, 'At least one AI flow is required'),
  prompts: z.array(promptExampleSchema).min(1, 'At least one prompt example is required'),
});

/**
 * Metric item schema
 */
export const metricItemSchema = z.object({
  name: z.string().min(1, 'Metric name is required'),
  value: z.string().min(1, 'Metric value is required'),
  color: z.string().optional(),
});

/**
 * Results section schema
 */
export const resultsSectionSchema = z.object({
  metrics: z.array(metricItemSchema).min(1, 'At least one metric is required'),
  highlights: z.array(z.string()).min(1, 'At least one highlight is required'),
  promptHighlights: z.array(z.string()).min(1, 'At least one prompt highlight is required'),
});

/**
 * Future Plans section schema
 */
export const futurePlansSectionSchema = z.object({
  shortTerm: z.array(z.string()).min(1, 'At least one short-term plan is required'),
  longTerm: z.array(z.string()).min(1, 'At least one long-term plan is required'),
});

/**
 * Poster sections schema
 */
export const posterSectionsSchema = z.object({
  background: backgroundSectionSchema,
  objectives: objectivesSectionSchema,
  aiUsage: aiUsageSectionSchema,
  results: resultsSectionSchema,
  futurePlans: futurePlansSectionSchema,
});

/**
 * Complete poster content schema
 */
export const posterContentSchema = z.object({
  meta: posterMetaSchema,
  sections: posterSectionsSchema,
  theme: themeVariantSchema,
  demoVideoUrl: z.string().optional(),
});

/**
 * Type inference from schema
 */
export type PosterContent = z.infer<typeof posterContentSchema>;
export type PosterMeta = z.infer<typeof posterMetaSchema>;
export type PosterSections = z.infer<typeof posterSectionsSchema>;
export type AIFlowItem = z.infer<typeof aiFlowItemSchema>;
export type PromptExample = z.infer<typeof promptExampleSchema>;
export type MetricItem = z.infer<typeof metricItemSchema>;
export type ThemeVariant = z.infer<typeof themeVariantSchema>;
export type BackgroundSection = z.infer<typeof backgroundSectionSchema>;
export type ObjectivesSection = z.infer<typeof objectivesSectionSchema>;
export type AIUsageSection = z.infer<typeof aiUsageSectionSchema>;
export type ResultsSection = z.infer<typeof resultsSectionSchema>;
export type FuturePlansSection = z.infer<typeof futurePlansSectionSchema>;

/**
 * Validate poster content safely
 * @param data - Unknown data to validate
 * @return Validation result with success flag and typed data or error
 */
export function validatePosterContent(data: unknown) {
  return posterContentSchema.safeParse(data);
}

/**
 * Parse and assert poster content (throws on error)
 * @param data - Unknown data to parse
 * @return Validated poster content
 * @throws ZodError if validation fails
 */
export function parsePosterContent(data: unknown): PosterContent {
  return posterContentSchema.parse(data);
}
