# Framer Motion

## Overview
Framer Motion is a production-ready motion library for React. It provides declarative animation APIs, gesture handling, and layout transitions.

## Version Info (2025)
- **Latest**: v12.x (major update with improved performance)
- **React 19 support**: Full support for React 19 features

## Installation
```bash
npm install framer-motion
```

## Basic Animations

### 1. Simple Animations
```tsx
import { motion } from 'framer-motion'

function FadeIn({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5 }}
    >
      {children}
    </motion.div>
  )
}
```

### 2. Variants (Predefined Animations)
```tsx
const variants = {
  hidden: { opacity: 0, x: -50 },
  visible: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 50 },
}

function ListItem({ text }: { text: string }) {
  return (
    <motion.li
      variants={variants}
      initial="hidden"
      animate="visible"
      exit="exit"
      transition={{ duration: 0.3 }}
    >
      {text}
    </motion.li>
  )
}
```

### 3. Staggered Animations
```tsx
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1, // Delay each child by 0.1s
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

function List({ items }: { items: string[] }) {
  return (
    <motion.ul
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {items.map((item) => (
        <motion.li key={item} variants={itemVariants}>
          {item}
        </motion.li>
      ))}
    </motion.ul>
  )
}
```

## Layout Animations

### 1. Layout (Automatic Layout Transitions)
```tsx
function Accordion() {
  const [isOpen, setIsOpen] = useState(false)
  
  return (
    <motion.div
      layout
      onClick={() => setIsOpen(!isOpen)}
      className="accordion"
    >
      <motion.div layout>{isOpen ? 'Close' : 'Open'}</motion.div>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          Accordion content
        </motion.div>
      )}
    </motion.div>
  )
}
```

### 2. AnimatePresence (Exit Animations)
```tsx
import { AnimatePresence } from 'framer-motion'

function TaskList({ tasks }: { tasks: string[] }) {
  return (
    <AnimatePresence mode="popLayout">
      {tasks.map((task) => (
        <motion.div
          key={task}
          layout
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ duration: 0.2 }}
        >
          {task}
        </motion.div>
      ))}
    </AnimatePresence>
  )
}
```

## Gestures

### 1. Drag
```tsx
function DraggableBox() {
  return (
    <motion.div
      drag
      dragConstraints={{ left: 0, right: 300, top: 0, bottom: 300 }}
      dragElastic={0.2}
      whileDrag={{ scale: 1.1 }}
      className="w-20 h-20 bg-blue-500"
    />
  )
}
```

### 2. Hover and Tap
```tsx
function InteractiveButton() {
  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 400, damping: 17 }}
    >
      Click me
    </motion.button>
  )
}
```

### 3. Pan (Swipe)
```tsx
function SwipeableCard() {
  const [x, setX] = useMotionValue(0)
  
  return (
    <motion.div
      style={{ x }}
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      onDragEnd={(event, info) => {
        if (info.offset.x > 100) {
          // Swiped right
          animate(x, 0)
        } else if (info.offset.x < -100) {
          // Swiped left
          animate(x, 0)
        }
      }}
    >
      Swipe me
    </motion.div>
  )
}
```

## Advanced Patterns

### 1. Custom Springs
```tsx
const spring = {
  type: 'spring',
  stiffness: 300,
  damping: 30,
  mass: 0.8,
}

function SpringAnimation() {
  return (
    <motion.div
      animate={{ rotate: 360 }}
      transition={spring}
    />
  )
}
```

### 2. Keyframes
```tsx
function KeyframeAnimation() {
  return (
    <motion.div
      animate={{
        scale: [1, 2, 2, 1, 1],
        rotate: [0, 0, 270, 270, 0],
        borderRadius: ['20%', '20%', '50%', '50%', '20%'],
      }}
      transition={{
        duration: 2,
        ease: 'easeInOut',
        times: [0, 0.2, 0.5, 0.8, 1],
        repeat: Infinity,
        repeatDelay: 1,
      }}
    />
  )
}
```

### 3. Path Animation
```tsx
import { motion } from 'framer-motion'
import { useRef, useEffect } from 'react'

function PathAnimation() {
  const pathRef = useRef<SVGPathElement>(null)
  const [pathLength, setPathLength] = useState(0)
  
  useEffect(() => {
    setPathLength(pathRef.current!.getTotalLength())
  }, [])
  
  return (
    <svg>
      <motion.path
        ref={pathRef}
        d="M0,0 L100,100"
        stroke="blue"
        strokeWidth={2}
        fill="transparent"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 2 }}
      />
    </svg>
  )
}
```

## Performance Considerations

### 1. Use Layout Animations Sparingly
Layout animations (using the `layout` prop) can be expensive. Use them only when necessary.

### 2. Use `will-change` CSS
```tsx
motion.div({
  // Will hint to browser to optimize
  style: { willChange: 'transform' }
})
```

### 3. Avoid Animate Property in Large Lists
For large lists, avoid using the `animate` prop on every item. Instead, use CSS animations or a library like `@tanstack/react-virtual`.

### 4. Use GPU Acceleration
Animate properties that use GPU acceleration:
- `transform` (translate, scale, rotate)
- `opacity`

Avoid animating:
- `width`, `height` (use layout prop instead)
- `top`, `left`, `right`, `bottom`

### 5. Reduce Re-renders
```tsx
// ❌ Re-renders on every frame
<motion.div animate={{ x: count }} />

// ✅ Use motion value directly
const x = useMotionValue(0)
<motion.div style={{ x }} />
```

## Common Pitfalls

### 1. Missing AnimatePresence for Exit Animations
```tsx
// ❌ Exit animation won't work
{isOpen && <motion.div exit={{ opacity: 0 }} />}

// ✅ Wrap in AnimatePresence
<AnimatePresence>
  {isOpen && <motion.div exit={{ opacity: 0 }} />}
</AnimatePresence>
```

### 2. Not Setting Unique Keys
```tsx
// ❌ Reordering won't animate properly
{items.map((item) => (
  <motion.div key={index}>{item}</motion.div>
))}

// ✅ Use unique keys
{items.map((item) => (
  <motion.div key={item.id}>{item.name}</motion.div>
))}
```

### 3. Animating Non-Transform Properties
```tsx
// ❌ Poor performance
<motion.div animate={{ width: 200 }} />

// ✅ Use layout prop for better performance
<motion.div layout animate={{ width: 200 }} />
```

## Official Resources
- [Framer Motion Documentation](https://www.framer.com/motion/)
- [GitHub Repository](https://github.com/framer/motion)
- [Examples](https://www.framer.com/motion/examples/)
