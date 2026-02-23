/**
 * Poster Generation CLI
 *
 * Main entry point for generating A0 posters from JSON content.
 * Usage: npm run generate <content-path> <output-path>
 */

import { promises as fs } from 'fs';
import { PosterRenderer } from '../renderer/renderer.js';
import { validatePosterContent } from '../domain/schema.js';

/**
 * CLI arguments
 */
interface GenerateArgs {
  /** Path to poster content JSON file */
  contentPath: string;
  /** Output filename for generated PPTX */
  outputPath: string;
  /** Generate QR code for demo video URL */
  generateQR?: boolean;
}

/**
 * Parse CLI arguments
 */
function parseArgs(): GenerateArgs {
  const args = process.argv.slice(2);

  return {
    contentPath: args[0] || 'posters/sit-copilot.json',
    outputPath: args[1] || 'sit-copilot-poster.pptx',
    generateQR: args.includes('--qr') || args.includes('-q'),
  };
}

/**
 * Load and validate poster content from JSON file
 * @param filePath - Path to JSON file
 * @returns Validated poster content
 */
async function loadContent(filePath: string) {
  console.log(`Loading content from: ${filePath}`);

  const contentRaw = await fs.readFile(filePath, 'utf-8');
  const contentJson = JSON.parse(contentRaw);

  // Validate content using Zod schema
  const validationResult = validatePosterContent(contentJson);

  if (!validationResult.success) {
    console.error('Content validation failed:');
    validationResult.error.errors.forEach((err) => {
      console.error(`  - ${err.path.join('.')}: ${err.message}`);
    });
    throw new Error('Invalid poster content');
  }

  console.log('✅ Content validated successfully');
  return validationResult.data;
}

/**
 * Generate QR code if demo video URL is present
 * @param content - Poster content
 */
async function generateQRIfNeeded(content: any): Promise<void> {
  const demoUrl = (content as any).demoVideoUrl;
  if (!demoUrl) {
    console.log('No demo video URL found, skipping QR code generation');
    return;
  }

  console.log(`Generating QR code for: ${demoUrl}`);

  try {
    const { generateDemoQRCode } = await import('../utils/qr-code.js');
    await generateDemoQRCode(demoUrl, 'assets/images/demo-qr.png');
  } catch (error) {
    console.warn(`Warning: Failed to generate QR code: ${error}`);
    console.warn('Continuing without QR code...');
  }
}

/**
 * Main generation function
 */
async function main(): Promise<void> {
  try {
    const args = parseArgs();

    console.log('='.repeat(50));
    console.log('SIT Copilot Poster Generator');
    console.log('='.repeat(50));

    // Load and validate content
    const content = await loadContent(args.contentPath);

    // Generate QR code if requested
    if (args.generateQR) {
      await generateQRIfNeeded(content);
    }

    // Render poster
    console.log('Generating poster...');
    const renderer = new PosterRenderer();
    await renderer.render(content, args.outputPath);

    console.log('='.repeat(50));
    console.log('✅ Poster generation complete!');
    console.log(`Output: ${args.outputPath}`);
    console.log('='.repeat(50));
  } catch (error) {
    console.error('❌ Generation failed:', error);
    process.exit(1);
  }
}

// Run if called directly
main();
