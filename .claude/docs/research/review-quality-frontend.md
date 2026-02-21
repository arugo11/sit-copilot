# Frontend Code Quality Review

**Date**: 2026-02-22
**Reviewer**: Quality Reviewer Agent
**Files Reviewed**: 35 TypeScript/TSX files

## Summary

The frontend codebase demonstrates **solid engineering practices** with good TypeScript usage, accessibility features, and React patterns. However, there are **16 findings** ranging from High to Low severity that should be addressed to improve code quality, maintainability, and performance.

**Overall Assessment**: 7/10 - Good foundation with room for improvement.

---

## Findings by Severity

### High Severity (2)

#### 1. ARIA Hidden on Dialog Container
**Files**: `src/components/ui/Modal.tsx:170`, `src/components/ui/SideSheet.tsx:169`

**Current Code**:
```tsx
<div
  className="fixed inset-0 z-50 flex items-center justify-center p-4"
  onClick={handleOverlayClick}
  aria-hidden="true"  // Problem: hides dialog from screen readers
>
```

**Issue**: The outer wrapper has `aria-hidden="true"` while containing the dialog. This can hide the dialog content from screen readers.

**Suggested Fix**:
```tsx
<div
  className="fixed inset-0 z-50 flex items-center justify-center p-4"
  onClick={handleOverlayClick}
>
  {/* Backdrop */}
  <div
    className="absolute inset-0 bg-fg-primary/50 backdrop-blur-sm"
    aria-hidden="true"  // Only on backdrop
  />
  <div ref={modalRef} role="dialog" ...>
```

---

#### 2. Hardcoded IDs Causing Collisions
**Files**: `src/components/ui/Modal.tsx:183`, `src/components/ui/Modal.tsx:197`, `src/components/ui/SideSheet.tsx:182`, `src/components/ui/SideSheet.tsx:199`

**Current Code**:
```tsx
<h2 id="modal-title" className="text-lg font-semibold">
  {title}
</h2>
```

**Issue**: Hardcoded IDs (`modal-title`, `sidesheet-title`) will collide when multiple instances render, breaking `aria-labelledby`.

**Suggested Fix**:
```tsx
import { useId } from 'react'

const titleId = useId()

<h2 id={titleId} className="text-lg font-semibold">
  {title}
</h2>
<div aria-labelledby={titleId} ...>
```

---

### Medium Severity (11)

#### 3. Stale Throttle Options in useLiveRegion
**File**: `src/hooks/useLiveRegion.ts:36`

**Current Code**:
```tsx
export function useLiveRegion(options: LiveRegionOptions = {}) {
  const { throttleMs = 5000, priority = 'polite' } = options

  const throttleRef = useRef(createAnnouncementThrottle(throttleMs))
  // throttleMs changes are ignored after initial creation
```

**Issue**: `createAnnouncementThrottle(throttleMs)` is created once in a ref, so later `throttleMs` changes are ignored.

**Suggested Fix**:
```tsx
const throttleRef = useRef<AnnouncementThrottle | null>(null)

useEffect(() => {
  throttleRef.current = createAnnouncementThrottle(throttleMs)
}, [throttleMs])
```

---

#### 4. Missing Cleanup in useLiveRegion
**File**: `src/hooks/useLiveRegion.ts:48`

**Issue**: Pending throttled announcements are never canceled on unmount.

**Suggested Fix**:
```tsx
useEffect(() => {
  return () => {
    throttleRef.current?.cancel()
  }
}, [])
```

---

#### 5. Keyboard Shortcuts Listener Churn
**File**: `src/hooks/useKeyboardShortcuts.ts:87`

**Issue**: Listener is re-bound whenever `shortcuts` identity changes; inline arrays/callbacks will churn global listeners and hurt performance.

**Suggested Fix**:
```tsx
const shortcutsRef = useRef(shortcuts)
useEffect(() => { shortcutsRef.current = shortcuts }, [shortcuts])

useEffect(() => {
  const handleKeyDown = (event: KeyboardEvent) => {
    for (const shortcut of shortcutsRef.current) {
      // ...
    }
  }
  document.addEventListener('keydown', handleKeyDown)
  return () => document.removeEventListener('keydown', handleKeyDown)
}, []) // Stable dependencies
```

---

#### 6. Inconsistent Modifier Key Handling
**File**: `src/hooks/useKeyboardShortcuts.ts:49, 52`

**Issue**: Modifier matching is inconsistent (`ctrl` checks `ctrlKey || metaKey`, then `meta` is checked separately).

**Suggested Fix**:
```tsx
// Define platform-aware helper
const isMod = event.ctrlKey || event.metaKey
// Use consistently in matching logic
```

---

#### 7. Tabs Props Design Issue
**File**: `src/components/ui/Tabs.tsx:28, 44`

**Issue**: `defaultTab` is required even in controlled mode (`activeTab` provided), which is awkward props design.

**Suggested Fix**:
```tsx
export interface TabsProps {
  tabs: TabProps[]
  activeTab?: string
  defaultTab?: string  // Make optional
  onChange?: (value: string) => void
}
```

---

#### 8. Tabs Focus Index Mismatch
**File**: `src/components/ui/Tabs.tsx:60, 98`

**Issue**: Keyboard navigation computes index from enabled tabs, but focus query uses all tabs, so focus can land on disabled buttons.

**Suggested Fix**:
```tsx
// Track refs per tab and focus by tab value
const tabRefs = useRef<Record<string, HTMLButtonElement>>({})

// Focus by value instead of index
tabRefs.current[enabledOptions[nextIndex].value]?.focus()
```

---

#### 9. SegmentedControl Focus Index Mismatch
**File**: `src/components/ui/SegmentedControl.tsx:41, 79`

**Issue**: Same enabled-index vs DOM-index mismatch as Tabs.

**Suggested Fix**: Same pattern as above (value-based refs).

---

#### 10. Toast Live Region Priority Not Updated
**File**: `src/components/common/Toast.tsx:45, 66`

**Issue**: Live region `aria-live` priority is only set when region is first created; later danger toasts may not be assertive.

**Suggested Fix**:
```tsx
const announceToScreenReader = useCallback((message: string, priority: 'polite' | 'assertive') => {
  let liveRegion = document.getElementById('toast-live-region')
  if (!liveRegion) {
    liveRegion = document.createElement('div')
    liveRegion.id = 'toast-live-region'
    // ...
  }

  // Update priority before announcing
  liveRegion.setAttribute('aria-live', priority)
  liveRegion.textContent = ''
  setTimeout(() => {
    liveRegion!.textContent = message
  }, 0)
}, [])
```

---

#### 11. Toast Context Causes Unnecessary Rerenders
**File**: `src/components/common/Toast.tsx:81`

**Issue**: Single context value includes both state and actions, so all consumers rerender whenever toast list changes.

**Suggested Fix**:
```tsx
// Split contexts
const ToastStateContext = createContext<ToastContextValue | undefined>(undefined)
const ToastActionsContext = createContext<Omit<ToastContextValue, 'toasts'> | undefined>(undefined)

export function useToast() {
  const state = useContext(ToastStateContext)
  const actions = useContext(ToastActionsContext)
  // ...
}
```

---

#### 12. Settings HasChanges Logic Flaw
**File**: `src/pages/settings/SettingsPage.tsx:58`

**Current Code**:
```tsx
const hasChanges = Object.keys(localChanges).length > 0
```

**Issue**: Toggling a value back to original still counts as dirty.

**Suggested Fix**:
```tsx
const hasChanges = useMemo(() => {
  return !shallowEqual(effectiveSettings, initialSettingsRef.current)
}, [effectiveSettings])
```

---

#### 13. Type Safety Issues in Settings
**File**: `src/pages/settings/SettingsPage.tsx:177, 197`

**Issue**: Type safety weakened by casts and broad `language?: string` typing.

**Suggested Fix**:
```tsx
// Narrow API types
export interface UserSettings {
  theme?: 'light' | 'dark' | 'high-contrast'
  language?: 'ja' | 'en'  // Narrow union
  fontSize?: 'small' | 'normal' | 'large'
  reducedMotion?: boolean
}

// Use typed options instead of casts
onChange={(e) => handleSettingChange('fontSize', e.target.value as 'small' | 'normal' | 'large')}
```

---

### Low Severity (3)

#### 14. Code Duplication in LecturesPage
**File**: `src/pages/lectures/LecturesPage.tsx` (multiple lines)

**Issue**: Repeated page header and duplicated filter button blocks across states.

**Suggested Fix**:
```tsx
// Extract shared components
function LecturesHeader() { /* ... */ }
function LectureFilters({ filter, setFilter }: Props) { /* ... */ }
```

---

#### 15. Modal/SideSheet Code Duplication
**Files**: `src/components/ui/Modal.tsx:32`, `src/components/ui/SideSheet.tsx:32`

**Issue**: Components are large and highly duplicated (scroll lock, focus trap, ESC, overlay click).

**Suggested Fix**:
```tsx
// Extract shared dialog behavior
function useDialogBehavior(isOpen: boolean, onClose: () => void) {
  // Scroll lock, focus trap, ESC handling
}

// Base dialog component
function BaseDialog({ children, onClose, isOpen, ... }: Props) {
  useDialogBehavior(isOpen, onClose)
  return <div>...</div>
}
```

---

#### 16. Toast Close Button Missing Type
**File**: `src/components/common/Toast.tsx:170, 188`

**Issue**: Close button lacks explicit `type="button"` and local `cn` duplicates shared utility.

**Suggested Fix**:
```tsx
<button
  type="button"  // Add explicit type
  onClick={() => onDismiss(toast.id)}
  // ...
>
```

---

## Additional Observations

### Positive Patterns
1. **Excellent Accessibility**: Comprehensive ARIA attributes, keyboard navigation, screen reader support
2. **TypeScript Usage**: Good type coverage with proper interfaces
3. **Component Design**: Well-separated concerns (components, hooks, lib utilities)
4. **Internationalization**: Proper i18n setup with locale-aware components

### Minor Style Notes
1. **Magic Numbers**: Some hardcoded timeout values (50, 5000, 300) could be extracted to constants
2. **CSS Classes**: Extensive use of Tailwind utility strings - consider component-specific class variants for complex buttons
3. **Empty Variant Prop**: `_variant` in `EmptyState.tsx:17` suggests incomplete refactoring

---

## Priority Action Items

1. **[HIGH]** Fix hardcoded IDs in Modal/SideSheet for accessibility
2. **[HIGH]** Remove incorrect `aria-hidden` from dialog wrappers
3. **[MEDIUM]** Fix `useLiveRegion` cleanup and stale options
4. **[MEDIUM]** Optimize `useKeyboardShortcuts` listener churn
5. **[MEDIUM]** Fix Toast context rerender issue
6. **[MEDIUM]** Improve Tabs/SegmentedControl focus handling

---

## Files Changed

No files were modified during this review. This is a read-only analysis.

---

## Recommendations

1. **Add ESLint Rules**: Consider adding `react-hooks/rules-of-hooks` and `jsx-a11y` rules
2. **Component Testing**: Add tests for keyboard navigation in Tabs/SegmentedControl
3. **Storybook**: Create stories for complex UI components to catch accessibility issues early
4. **Performance Audit**: Consider React DevTools Profiler for the shortcuts hook issue
5. **Code Review Checklist**: Add accessibility checklist for dialog components
