# Frontend Security Review

**Review Date:** 2026-02-22
**Reviewer:** Security Reviewer Agent
**Scope:** 35 TypeScript files in `/home/argo/sit-copilot/frontend/src/`

---

## Executive Summary

**Overall Risk Level: LOW**

The frontend codebase demonstrates good security practices overall. No critical or high-severity vulnerabilities were found. The code follows React best practices with proper type safety, no hardcoded credentials, and appropriate use of React's built-in XSS protections. Several medium and low-priority recommendations are provided for additional hardening.

---

## Detailed Findings

### 1. No Hardcoded Secrets or Credentials

**Status: PASS**

- No API keys, secrets, or credentials hardcoded in any source files
- API base URL uses environment variable (`VITE_API_BASE_URL`) with fallback to localhost
- Proper separation of configuration from code

**Reference:** `src/lib/api/client.ts:6`

```typescript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
```

---

### 2. XSS (Cross-Site Scripting) Protection

**Status: PASS - React Provides Default Protection**

**Analysis:**
- React automatically escapes content in JSX by default
- No use of `dangerouslySetInnerHTML` found in any components (35 files reviewed)
- User input is rendered through React's `{variable}` syntax which escapes HTML entities
- i18next configured with `escapeValue: false` which is safe since React handles escaping

**Reference:** `src/lib/i18n/index.ts:31-32`

```typescript
interpolation: {
  escapeValue: false, // React already escapes
}
```

**Note:** This is correct because React's escaping is sufficient. Double-escaping would cause display issues.

---

### 3. Input Validation Gaps

**Severity: MEDIUM**

**Finding 3.1: Lecture ID from URL Parameter Not Validated**

**Location:** Multiple files use `useParams()` or route params without validation
- `src/pages/lectures/LectureLivePage.tsx` - Uses `:id` from route
- `src/pages/lectures/LectureReviewPage.tsx` - Uses `:id` from route
- `src/pages/lectures/LectureSourcesPage.tsx` - Uses `:id` from route

**Issue:** Route parameters are used directly without format validation before being passed to API calls.

**Risk:** Potential for API abuse with malformed IDs, though backend should validate.

**Recommendation:**
```typescript
// Add validation before API calls
function validateLectureId(id: string): boolean {
  // Example: Validate UUID format or expected ID pattern
  return /^[a-zA-Z0-9-]{1,50}$/.test(id)
}
```

---

**Finding 3.2: User Input in QA Questions Not Length-Validated**

**Location:** `src/pages/lectures/LectureLivePage.tsx:103-107`, `src/pages/lectures/LectureReviewPage.tsx:69-72`

**Issue:** Question input textareas have no client-side max length validation.

**Recommendation:**
```typescript
<textarea
  maxLength={5000}  // Add reasonable max length
  className="input min-h-24"
  placeholder="講義について質問を入力してください..."
/>
```

---

### 4. Authentication / Authorization

**Severity: MEDIUM**

**Finding 4.1: No Authentication Implementation**

**Location:** Entire frontend

**Issue:**
- LandingPage has "Login with university account" button that is non-functional (no auth handler)
- No authentication state management detected
- No token storage or refresh logic
- All API calls in `src/lib/api/hooks.ts` lack authentication headers

**Risk:** Application appears to be in development/demo mode with no actual authentication.

**Recommendation:**
1. Implement authentication flow (likely OAuth2 for university SSO)
2. Add JWT/access token storage (httpOnly cookies preferred over localStorage)
3. Add auth interceptor to API client for automatic token injection
4. Implement protected route wrapper component

```typescript
// Example: Add auth token to requests
private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken() // from secure cookie
  const config: RequestInit = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
      ...options.headers,
    },
  }
  // ...
}
```

---

### 5. Sensitive Data Exposure in Logs/Errors

**Severity: LOW**

**Finding 5.1: Error Messages May Expose Internal Information**

**Location:** `src/lib/api/hooks.ts:38-45`

```typescript
function handleApiError(error: unknown, context: string): string {
  if (error instanceof ApiError) {
    return error.message  // May contain internal details
  }
  // ...
}
```

**Issue:** Error messages from API are directly displayed to users via toasts.

**Recommendation:**
- Sanitize error messages before displaying
- Log full errors to monitoring service
- Show user-friendly messages only

---

### 6. Dependency Vulnerabilities

**Severity: MEDIUM (Requires External Scan)**

**Current Dependencies (from package.json):**
- `@tanstack/react-query: ^5.90.21`
- `i18next: ^25.8.13`
- `react: ^19.2.0`
- `react-dom: ^19.2.0`
- `react-router-dom: ^7.13.0`
- `vite: ^7.3.1`

**Recommendation:**
Run dependency audit:
```bash
npm audit
# or for more detailed report
npm audit --audit-level=moderate
```

---

### 7. API Key/Endpoint Exposure

**Severity: LOW**

**Finding 7.1: API Endpoints Predictable**

**Location:** `src/lib/api/client.ts`

**Issue:** API endpoints are hardcoded and predictable.

**Risk:** Low - this is standard practice. Backend must implement proper rate limiting and authentication.

**Finding 7.2: No Request Rate Limiting**

**Issue:** Frontend makes no attempt to rate limit requests.

**Recommendation:** Consider implementing client-side rate limiting for expensive operations (e.g., QA questions) to improve UX and reduce server load.

---

### 8. CSRF (Cross-Site Request Forgery) Protection

**Severity: LOW**

**Current State:** No CSRF tokens detected in API requests.

**Recommendation:**
- Backend should implement CSRF protection for state-changing operations
- If using cookies for authentication, ensure `SameSite` attribute is set
- Consider adding CSRF token to API client for mutation requests

---

### 9. Content Security Policy (CSP) Considerations

**Severity: LOW**

**Finding 9.1: No CSP Meta Tag**

**Location:** `index.html`

**Issue:** No Content-Security-Policy meta tag defined.

**Recommendation:**
Add CSP meta tag to `index.html`:
```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://api.example.com;">
```

---

### 10. localStorage Security Considerations

**Severity: LOW**

**Finding 10.1: Theme Stored in localStorage**

**Location:** `src/contexts/ThemeContext.tsx:33-42`

```typescript
const stored = localStorage.getItem(THEME_STORAGE_KEY)
if (stored && isValidTheme(stored)) {
  return stored as Theme
}
```

**Analysis:**
- Good: Type validation (`isValidTheme`) before using stored value
- Low risk: Theme preference is not sensitive data

**Finding 10.2: i18next Language Detection Uses localStorage**

**Location:** `src/lib/i18n/index.ts:35-38`

**Analysis:** Standard practice, low risk.

---

### 11. Additional Security Good Practices Observed

1. **Type Safety:** Comprehensive TypeScript usage prevents many runtime vulnerabilities
2. **Accessibility:** Proper ARIA attributes throughout
3. **Error Boundaries:** React Query configured with retry behavior
4. **No Inline Event Handlers in JSX String Attributes** (all use proper handlers)
5. **Focus Management:** Proper focus trap in modals prevents clickjacking issues
6. **No `eval()` or Function Constructor usage**

---

## Recommendations by Priority

### High Priority
1. **Implement Authentication** - Application currently has no auth mechanism

### Medium Priority
2. **Add Input Validation** - Validate route params and form inputs before API calls
3. **Add Request Length Limits** - Prevent abuse with max-length attributes
4. **Sanitize Error Messages** - Don't display raw API errors to users
5. **Run `npm audit`** - Check for vulnerable dependencies

### Low Priority
6. **Add CSP Meta Tag** - Defense in depth against XSS
7. **Add Client-Side Rate Limiting** - Improve UX, reduce server load
8. **Add CSRF Tokens** - If using cookie-based authentication

---

## Conclusion

The frontend codebase is well-structured with good security fundamentals. The main gap is the lack of authentication implementation, which appears to be intentional for the current development/demo phase. Once authentication is added, the remaining priority should be input validation and error message sanitization.

**No critical or high-severity vulnerabilities requiring immediate remediation were found.**
