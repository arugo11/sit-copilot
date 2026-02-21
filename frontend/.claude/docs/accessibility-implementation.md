# Frontend Accessibility Implementation

## Summary

Enhanced accessibility features across the frontend based on `docs/frontend.md` Section 10 requirements.

## Files Created/Modified

### New Files

1. **`src/lib/a11y/index.ts`** - Core accessibility utilities
   - `announceToScreenReader()` - Live region announcements
   - `prefersReducedMotion()` - Detect motion preferences
   - `getFocusableElements()` - Query focusable elements
   - `trapFocus()` - Focus trap for modals
   - `createFocusTrap()` - Focus trap controller
   - `createAnnouncementThrottle()` - Throttled announcements (5s min per spec)
   - `announceConnectionState()` - Connection state announcements
   - `keyboardShortcuts` - Predefined shortcuts with descriptions

2. **`src/hooks/useLiveRegion.ts`** - Live region hooks
   - `useLiveRegion()` - Generic announcement hook
   - `useConnectionAnnouncer()` - Connection state announcements
   - `useQaAnnouncer()` - QA status announcements

3. **`src/hooks/useFocusTrap.ts`** - Focus management hooks
   - `useFocusTrap()` - Trap focus within container
   - `useFocusReturn()` - Return focus on close
   - `useAutoFocus()` - Auto-focus on mount

4. **`src/hooks/useKeyboardShortcuts.ts`** - Keyboard navigation
   - `useKeyboardShortcuts()` - Register keyboard shortcuts
   - `useKeyboardNavigation()` - List navigation with arrow keys

5. **`src/hooks/index.ts`** - Hooks barrel export

6. **`src/components/common/KeyboardShortcutsHelp.tsx`** - Keyboard shortcuts display
   - `KeyboardShortcutsHelp` - Display available shortcuts
   - `KeyboardShortcutButton` - Button to open shortcuts modal
   - `lectureShortcuts` - Predefined shortcuts for the app

7. **`src/components/common/IconButton.tsx`** - Accessible icon buttons
   - `IconButton` - Icon-only button with required aria-label
   - `IconButtonWithTooltip` - Icon button with tooltip
   - `IconTextButton` - Button with icon and text

8. **`src/components/ui/FormField.tsx`** - Accessible form components
   - `FormField` - Form field wrapper with ARIA attributes
   - `TextInput` - Text input with label, description, error
   - `TextArea` - Textarea with full accessibility
   - `Select` - Select dropdown with ARIA
   - `Checkbox` - Checkbox with proper labeling

### Modified Files

1. **`src/components/common/AppShell.tsx`**
   - Added skip to main content link
   - Added semantic roles (banner, main, complementary)
   - Added separate live regions (polite + assertive)
   - Added connection state support
   - Added aria-label for sidebar regions

2. **`src/components/common/Toast.tsx`**
   - Integrated live region announcements
   - Added status icons for each variant
   - Improved close button accessibility
   - Icons now have aria-hidden="true"

3. **`src/styles/globals.css`**
   - Added `.focus\:not-sr-only` for skip links
   - Added `.visually-hidden` alternative
   - Added `*:focus:not(:focus-visible)` to remove outline for mouse users
   - Added `.skip-link` styling

## Accessibility Features Implemented

### 1. Live Region Support (Section 10.5)

- **Polite live region** - General announcements
- **Assertive live region** - Important/error messages
- **Connection status region** - Dedicated for connection state
- **Throttled announcements** - Loading announcements limited to 5s intervals
- **Toast integration** - All toasts announced to screen readers

### 2. Keyboard Navigation (Section 10.4)

- **Focus trap** - Modal/SideSheet already implemented, now extracted as reusable hook
- **Skip to main content** - AppShell includes skip link
- **Arrow key navigation** - useKeyboardNavigation for lists
- **Global shortcuts** - Predefined shortcuts for common actions
- **Focus ring** - Visible on all interactive elements

### 3. Focus Management

- **useFocusTrap** - Reusable focus trap for any container
- **useFocusReturn** - Returns focus to trigger element on close
- **useAutoFocus** - Auto-focus elements on mount
- **Mutation observer** - Updates focusable elements when DOM changes

### 4. ARIA Labels

- **IconButton** - Requires aria-label (enforced by TypeScript)
- **FormField** - Proper aria-labelledby, aria-describedby
- **Error messages** - aria-errormessage + role="alert"
- **Regions** - role="region" with aria-label for major sections
- **Icons** - aria-hidden="true" for decorative icons

### 5. Reduced Motion (Section 10.6)

- **prefers-reduced-motion** - Already in globals.css
- **Respects OS setting** - All animations respect this
- **Motion utilities** - `prefersReducedMotion()` check available

## Usage Examples

### Announcing to Screen Readers

```tsx
import { useLiveRegion } from '@/hooks'

function MyComponent() {
  const { announce } = useLiveRegion()

  const handleSubmit = () => {
    // ... do work
    announce('Saved successfully', 'polite')
  }
}
```

### Connection State Announcements

```tsx
import { useConnectionAnnouncer } from '@/hooks'
import { AppShell } from '@/components/common'

function App() {
  const { announceConnection } = useConnectionAnnouncer()
  const [connectionState, setConnectionState] = useState('connecting')

  useEffect(() => {
    announceConnection(connectionState)
  }, [connectionState, announceConnection])

  return (
    <AppShell connectionState={connectionState}>
      {/* ... */}
    </AppShell>
  )
}
```

### Accessible Form Fields

```tsx
import { TextInput, TextArea } from '@/components/ui'

function QuestionForm() {
  const [question, setQuestion] = useState('')
  const [error, setError] = useState('')

  return (
    <>
      <TextInput
        label="Your Question"
        description="Ask about the lecture content"
        error={error}
        required
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />
    </>
  )
}
```

### Keyboard Shortcuts

```tsx
import { useKeyboardShortcuts } from '@/hooks'
import { KeyboardShortcutsHelp, lectureShortcuts } from '@/components/common'

function MyComponent() {
  const [isHelpOpen, setIsHelpOpen] = useState(false)

  useKeyboardShortcuts([
    { key: 'Ctrl+K', callback: () => console.log('Search opened') },
    { key: '?', callback: () => setIsHelpOpen(true) },
  ])

  return (
    <Modal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} title="Keyboard Shortcuts">
      <KeyboardShortcutsHelp shortcuts={lectureShortcuts} />
    </Modal>
  )
}
```

### Icon Button

```tsx
import { IconButton } from '@/components/common'

function CloseButton({ onClose }) {
  return (
    <IconButton
      icon={<CloseIcon />}
      aria-label="Close dialog"
      onClick={onClose}
      variant="ghost"
    />
  )
}
```

## Predefined Keyboard Shortcuts

| Key Combination | Action (JA) | Action (EN) |
|-----------------|-------------|-------------|
| `/` | 検索ボックスにフォーカス | Focus search |
| `Escape` | ダイアログを閉じる | Close dialog |
| `Arrow Up/Down` | 字幕をスクロール | Scroll transcript |
| `Ctrl+K` | 質問入力を開く | Open question input |
| `Ctrl+,` | 設定を開く | Open settings |
| `Enter` | 質問を送信 | Submit question |
| `Ctrl+Shift+T` | テーマを切り替え | Toggle theme |
| `Ctrl+=` | 文字サイズを拡大 | Increase font size |
| `Ctrl+-` | 文字サイズを縮小 | Decrease font size |

## WCAG 2.2 AA Compliance

The implementation covers:

- **1.3.1 Info and Relationships** - Semantic HTML, ARIA labels
- **1.3.2 Meaningful Sequence** - Logical tab order, focus management
- **1.4.3 Contrast (Minimum)** - 4.5:1 for text, 3:1 for UI
- **1.4.11 Non-text Contrast** - Icons and focus indicators
- **1.4.12 Text Spacing** - Proper spacing in design tokens
- **1.4.13 Content on Hover/Focus** - No dismiss on hover
- **2.1.1 Keyboard** - All functions available via keyboard
- **2.1.2 No Keyboard Trap** - Focus trap with ESC escape
- **2.1.4 Character Key Shortcuts** - Can be remapped/disabled
- **2.4.3 Focus Order** - Logical focus order
- **2.5.5 Target Size** - 40x40 minimum for interactive elements
- **4.1.2 Name, Role, Value** - Proper ARIA attributes

## Testing Checklist

- [ ] Navigate entire app with keyboard only
- [ ] All interactive elements have visible focus ring
- [ ] Screen reader announces all toasts and status changes
- [ ] Skip link works and focuses main content
- [ ] Modals trap focus and return on close
- [ ] Form fields have proper labels and error announcements
- [ ] Icon buttons have aria-label
- [ ] Reduced motion setting is respected
- [ ] All major regions have role and aria-label
- [ ] Connection state changes are announced
