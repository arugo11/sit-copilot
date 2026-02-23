/**
 * QR Code Generation Utility
 *
 * Generates QR codes for demo video links and other URLs.
 */

import QRCode from 'qrcode';
import { promises as fs } from 'fs';
import { join } from 'path';

/**
 * QR code generation options
 */
export interface QRCodeOptions {
  /** URL to encode in QR code */
  url: string;
  /** Output file path (relative to project root) */
  outputPath: string;
  /** Size of QR code in pixels */
  size?: number;
  /** Margin around QR code */
  margin?: number;
  /** Dark color (hex) */
  darkColor?: string;
  /** Light color (hex) */
  lightColor?: string;
}

/**
 * Generate a QR code image
 * @param options - QR code generation options
 */
export async function generateQRCode(options: QRCodeOptions): Promise<void> {
  const {
    url,
    outputPath,
    size = 512,
    margin = 2,
    darkColor = '#000000',
    lightColor = '#FFFFFF',
  } = options;

  try {
    // Generate QR code as data URL
    const qrDataUrl = await QRCode.toDataURL(url, {
      width: size,
      margin,
      color: {
        dark: darkColor,
        light: lightColor,
      },
    });

    // Extract base64 data and save as PNG
    const base64Data = qrDataUrl.split(',')[1];
    const buffer = Buffer.from(base64Data, 'base64');

    // Ensure directory exists
    const dir = join(process.cwd(), outputPath).split('/').slice(0, -1).join('/');
    await fs.mkdir(dir, { recursive: true });

    // Write file
    await fs.writeFile(join(process.cwd(), outputPath), buffer);

    console.log(`QR code generated: ${outputPath}`);
  } catch (error) {
    console.error(`Failed to generate QR code: ${error}`);
    throw error;
  }
}

/**
 * Generate QR code for demo video
 * @param url - Demo video URL
 * @param outputPath - Output path (default: assets/images/demo-qr.png)
 */
export async function generateDemoQRCode(
  url: string,
  outputPath = 'assets/images/demo-qr.png',
): Promise<void> {
  await generateQRCode({
    url,
    outputPath,
    size: 512,
    margin: 2,
    darkColor: '#0F2742', // Primary color
    lightColor: '#FFFFFF',
  });
}

/**
 * CLI entry point for QR code generation
 */
export async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const url = args[0] || 'https://example.com/demo-video';
  const outputPath = args[1] || 'assets/images/demo-qr.png';

  await generateDemoQRCode(url, outputPath);
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(console.error);
}
