# PptxGenJS Library Documentation

## Overview

PptxGenJS is a JavaScript library for creating PowerPoint presentations programmatically. It works in both browser and Node.js environments.

## Features

- Presentation creation with metadata (author, subject, revision)
- Text, images, shapes, tables, and charts
- Master slides for consistent branding
- Custom layouts and dimensions
- Rich text formatting
- HTML to PowerPoint conversion
- Cross-platform (browser + Node.js)

## Quick Start

```javascript
// 1. Initialize
let pptx = new PptxGenJS();
pptx.layout = '16x9';

// 2. Add slide
let slide = pptx.addSlide();

// 3. Add content
slide.addText("Hello World", { x: 1, y: 1, w: 5, h: 1 });

// 4. Save
pptx.writeFile({ fileName: "presentation.pptx" });
```

## Master Slides

Define reusable templates:

```javascript
pptx.defineSlideMaster({
  title: 'MASTER_SLIDE',
  background: { color: 'F1F1F1' },
  objects: [
    { 
      image: { 
        x: 11.5, 
        y: 5.9, 
        w: 1.67, 
        h: 0.75, 
        path: 'path/to/logo.png' 
      } 
    },
    { 
      text: { 
        text: 'Confidential', 
        options: { 
          x: 0, 
          y: 6.9, 
          w: '100%', 
          align: 'center', 
          color: 'A9A9A9', 
          fontSize: 12 
        } 
      } 
    }
  ],
  slideNumber: { x: 0.3, y: '95%' }
});

// Apply master
let slide = pptx.addSlide({ masterName: 'MASTER_SLIDE' });
```

## Positioning & Units

- Default unit: **inches**
- Can use percentages: `'50%'`
- Properties: `x`, `y` (position), `w`, `h` (size)

```javascript
// Absolute positioning (inches)
slide.addText("Hello", { x: 1.5, y: 1.5 });

// Percentage-based (responsive)
slide.addText("Centered", { x: '50%', y: 3 });
```

## Text Formatting

```javascript
// Simple text
slide.addText("Simple text", { x: 1, y: 1, w: 5, h: 1 });

// Rich text with mixed formatting
slide.addText(
  [
    { text: "This is ", options: { fontSize: 24, color: "363636" } },
    { text: "bold", options: { fontSize: 24, bold: true, color: "FF0000" } },
    { text: " and ", options: { fontSize: 24 } },
    { text: "italic", options: { fontSize: 24, italic: true } }
  ],
  { x: 1, y: 1, w: 8, h: 1, align: 'center' }
);

// Text box options
slide.addText("Styled text", {
  x: 1, y: 2, w: 8, h: 1.5,
  fontSize: 32,
  fontFace: "Arial",
  color: "363636",
  bold: true,
  italic: false,
  underline: false,
  align: "center",       // left, center, right, justify
  valign: "middle",      // top, middle, bottom
  fill: { color: "F1F1F1" },
  line: { type: "solid", color: "000000", width: 1 }
});
```

## Images

```javascript
// From URL
slide.addImage({
  path: "https://example.com/image.png",
  x: 1, y: 1, w: 5, h: 3
});

// From base64
slide.addImage({
  data: "image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
  x: 1, y: 1, w: 5, h: 3
});

// With sizing options
slide.addImage({
  path: "image.png",
  x: 1, y: 1,
  w: 5, h: 3,
  sizing: { type: "contain", w: 5, h: 3 }  // contain, cover
});
```

## Shapes

```javascript
// Rectangle
slide.addShape(pptx.shapes.RECTANGLE, {
  x: 1, y: 1, w: 8, h: 4,
  fill: { color: "F1F1F1" },
  line: { color: "000000", width: 1 }
});

// Circle (ellipse with equal w/h)
slide.addShape(pptx.shapes.ELLIPSE, {
  x: 1, y: 1, w: 2, h: 2,
  fill: { color: "FF0000" }
});

// Line
slide.addShape(pptx.shapes.LINE, {
  x: 1, y: 1, w: 8, h: 0,
  line: { color: "000000", width: 2, dashType: "dash" }
});
```

## Tables

```javascript
let tabRows = [
  [
    { text: "Name", options: { bold: true, fontSize: 18 } },
    { text: "Age", options: { bold: true, fontSize: 18 } },
    { text: "City", options: { bold: true, fontSize: 18 } }
  ],
  ["Alice", 30, "New York"],
  ["Bob", 25, "London"]
];

slide.addTable(tabRows, {
  x: 1, y: 1, w: 8,
  border: { pt: 1, color: "000000" },
  fill: { color: "F1F1F1" },
  align: "center",
  valign: "middle"
});
```

## Custom Layout for A0 Poster

```javascript
// A0 dimensions in inches (841mm x 1189mm ≈ 33.1" x 46.8")
let pptx = new PptxGenJS();
pptx.defineLayout({ name: 'A0', width: 33.1, height: 46.8 });
pptx.layout = 'A0';

// Create poster slide
let poster = pptx.addSlide();
```

## Best Practices

1. **Use Master Slides** for consistent branding
2. **Use Percentages** for flexible positioning
3. **Define Custom Layouts** for non-standard sizes
4. **TypeScript Support** - use for type safety
5. **Method Chaining** for cleaner code

## Limitations

- No auto-sizing of text boxes - must define dimensions
- Chart limitations (no rotated line charts)
- HTML-to-PPT has limitations on complex styling

## Color Schemes for Academic Posters

```javascript
const COLORS = {
  primary: "0B3D91",    // Dark Blue - headers
  accent: "FFC20E",     // Yellow - highlights
  text: "333333",       // Dark Gray - body text
  background: "F8F9FA", // Light Gray - sections
  highlight: "E2EFDA",  // Light Green - callouts
  white: "FFFFFF"
};
```

## Font Size Guidelines for A0 Poster

```javascript
const FONTS = {
  title: 88,           // Main title
  author: 56,          // Author names
  section: 48,         // Section headers
  subsection: 36,      // Subsection headers
  body: 24,            // Body text (minimum)
  caption: 18          // Figure captions
};
```

## A0 Poster Structure Example

```javascript
let pptx = new PptxGenJS();
pptx.layout = { name: 'A0', width: 33.1, height: 46.8 };

// Define master slide with university branding
pptx.defineSlideMaster({
  title: 'POSTER_MASTER',
  background: { color: 'FFFFFF' },
  objects: [
    { text: { text: 'Conference Name | 2026', options: {
      x: 0, y: 46, w: '100%', align: 'center', color: 'A9A9A9', fontSize: 18
    }}}
  ]
});

let poster = pptx.addSlide({ masterName: 'POSTER_MASTER' });

// Title section
poster.addText('SIT Copilot: AI-Powered Lecture Support System', {
  x: 1, y: 1, w: 31.1, h: 3,
  fontSize: 80, bold: true, align: 'center', color: COLORS.primary
});

// Three-column layout for content
const colWidth = 10;
const gap = 0.5;
const startX = 1;
const startY = 6;

// Left column
poster.addText('Background', { x: startX, y: startY, fontSize: 48, bold: true });
// ... add content

// Center column (with architecture diagram)
poster.addText('System Architecture', { x: startX + colWidth + gap, y: startY, fontSize: 48, bold: true });
// ... add diagram

// Right column
poster.addText('Results', { x: startX + (colWidth + gap) * 2, y: startY, fontSize: 48, bold: true });
// ... add results
```

## Best Practices

1. **Use Master Slides** for consistent branding
2. **Use Percentages** for flexible positioning
3. **Define Custom Layouts** for non-standard sizes
4. **TypeScript Support** - use for type safety
5. **Method Chaining** for cleaner code
6. **For A0 Posters**: Use 3-column layout, define color constants, use larger font sizes
7. **Visual Hierarchy**: Title > Section > Subsection > Body > Caption

## Limitations

- No auto-sizing of text boxes - must define dimensions
- Chart limitations (no rotated line charts)
- HTML-to-PPT has limitations on complex styling
- Large images can increase file size significantly

## Resources

- Official docs: https://gitbrent.github.io/PptxGenJS/
- GitHub: https://github.com/gitbrent/PptxGenJS
- TypeScript types included in package
