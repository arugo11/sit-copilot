# Academic Poster Design Research

## Summary

Effective academic posters prioritize clarity, brevity, and visual appeal. The goal is to create a "visual abstract" that serves as a conversation starter, not a comprehensive document.

## A0 Poster Specifications

- **Dimensions**: 841mm x 1189mm (33.1" x 46.8")
- **Orientation**: Portrait (most common) or Landscape (check conference guidelines)
- **Safe area**: Keep content 20-30mm from edges
- **Resolution**: Images at least 300 DPI

## Layout Principles

### Grid System

- Use 3-4 column grid for A0 portrait
- Maintain consistent margins and spacing
- 40% white space (don't overcrowd)
- Align all elements to grid

### Standard Structure

```
+--------------------------------------------------+
|                   HEADER                         |
|  Title | Authors | Affiliations | Logo          |
+--------------------------------------------------+
|  Intro  |  Methods  |  Results  |  Discussion   |
|         |           |          |               |
|         |           |          |               |
+--------------------------------------------------+
|       Conclusions | References | Acknowledgments|
+--------------------------------------------------+
```

### Visual Hierarchy

1. **Title** - Largest, most prominent (72-100pt)
2. **Section headings** - Secondary (48-60pt)
3. **Body text** - Tertiary (24-36pt)
4. **Captions** - Smallest (18-24pt)

### Reading Flow

- **Z-pattern**: Top-left → Top-right → Diagonal to bottom-left → Bottom-right
- **F-pattern**: For text-heavy sections
- **Central focus**: Place most important finding in center

## Typography

### Font Selection

| Use | Recommended Fonts |
|-----|-------------------|
| Titles | Arial, Helvetica, Calibri (sans-serif) |
| Body | Arial, Calibri, or Garamond (serif OK) |
| Monospace | Courier, Consolas (for code/data) |

**Rule**: Maximum 2 font families

### Font Sizes (A0 Poster)

| Element | Font Size |
|---------|-----------|
| Main Title | 72-100 pt |
| Section Headers | 48-60 pt |
| Subheaders | 36-44 pt |
| Body Text | 24-36 pt |
| Captions | 18-24 pt |
| References | 16-20 pt |

**Test**: Body text should be readable from 1-2 meters

### Best Practices

- Use **sentence case** for titles (not ALL CAPS)
- Left-align body text (never full-justify for posters)
- Increase line spacing (1.2-1.5)
- Use bold for emphasis, not underline

## Color Theory

### Palette Guidelines

- **2-3 colors maximum** (plus neutral backgrounds)
- **Primary**: Main brand/identity color
- **Secondary**: Accent for highlights
- **Neutral**: White/light gray backgrounds

### Accessibility

- **Contrast ratio**: Minimum 4.5:1 for body text
- **Color blindness**: Avoid red-green combinations
- **Test**: Use patterns + colors in charts (not color alone)

### Recommended Palettes

| Type | Colors |
|------|--------|
| Scientific | Blue (#0056b3) + Gray (#6c757d) + White |
| Medical | Teal (#009688) + Navy (#001f3f) + White |
| Engineering | Orange (#fd7e14) + Dark Blue (#003366) + White |

## Visual Content

### Image Guidelines

- **Resolution**: 300 DPI minimum at print size
- **Format**: PNG for graphics, JPG for photos
- **File size**: Keep individual images under 5MB
- **Placement**: 30-40% of poster should be visuals

### Figure Design

1. **Clear captions** - Self-explanatory without reading text
2. **High contrast** - Avoid dark backgrounds
3. **Minimal text in figures** - Save details for body
4. **Consistent styling** - Same color scheme across all figures

### Chart Best Practices

- Use bar charts for comparisons
- Use line charts for trends
- Use pie charts rarely (only for parts-of-whole)
- Always label axes clearly
- Include error bars for scientific data

## Common Mistakes

### Top 10 Errors

1. **Too much text** - "Wall of text" effect
2. **Font too small** - Unreadable from distance
3. **Poor quality images** - Pixelated or blurry
4. **Inconsistent styling** - Multiple fonts/colors
5. **No visual hierarchy** - Everything same size
6. **Cluttered layout** - Not enough white space
7. **Low contrast** - Text hard to read
8. **Missing conclusions** - Results without interpretation
9. **Too many colors** - Rainbow effect
10. **No flow** - Confusing reading order

### Before Printing Checklist

- [ ] Title readable from 3+ meters
- [ ] Body text readable from 1-2 meters  
- [ ] All images 300+ DPI
- [ ] Contrast ratio 4.5:1 minimum
- [ ] Maximum 2-3 colors
- [ ] Consistent spacing and alignment
- [ ] Clear visual hierarchy
- [ ] Flow from top-left to bottom-right
- [ ] Contact information included
- [ ] References formatted correctly

## Award-Winning Examples

### Resources

1. **University of Texas Austin Poster Samples**
   - https://ugs.utexas.edu/our/poster/samples
   - Includes critiques and explanations

2. **Animate Your Science**
   - https://www.animateyour.science/post/how-to-design-an-award-winning-conference-poster
   - Analysis of successful poster elements

3. **Better Poster Movement**
   - Search "#betterposter" for modern, single-message designs
   - Focuses on one main finding in large text

### "Better Poster" Design

```
+------------------------------------------+
|           HUGE MAIN FINDING             |
|            (72-100pt, bold)             |
|                                          |
|  [Central visual showing result]         |
|                                          |
|  Brief context | Brief methods | Impact  |
+------------------------------------------+
```

## PptxGenJS for Posters

### A0 Setup

```javascript
// A0 in inches
pptx.defineLayout({ 
  name: 'A0', 
  width: 33.1, 
  height: 46.8 
});
pptx.layout = 'A0';
```

### Column Layout Pattern

```javascript
// 3-column layout for A0 portrait
const colWidth = 9.5;  // inches
const colSpacing = 0.5;
const startX = 1.0;

// Column 1
slide.addText("Introduction", { x: startX, y: 3, w: colWidth, h: 0.5 });
// Column 2  
slide.addText("Methods", { x: startX + colWidth + colSpacing, y: 3, w: colWidth, h: 0.5 });
// Column 3
slide.addText("Results", { x: startX + (colWidth + colSpacing) * 2, y: 3, w: colWidth, h: 0.5 });
```

## References

- MIT Academic Poster Guide
- IEEE Poster Design Guidelines
- Nature "Points of View" column on poster design
- PptxGenJS Documentation: https://gitbrent.github.io/PptxGenJS/
