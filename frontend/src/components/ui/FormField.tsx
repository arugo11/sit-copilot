/**
 * FormField Component
 * Accessible form field with label, description, and error messages
 * Based on docs/frontend.md Section 10.1 and WCAG 2.2 AA
 */

import type { ReactNode, InputHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
import { generateA11yId } from '@/lib/a11y'

export interface FormFieldProps {
  /** Field label */
  label: string
  /** Field identifier */
  id?: string
  /** Optional description text */
  description?: string
  /** Error message */
  error?: string
  /** Whether the field is required */
  required?: boolean
  /** Additional CSS classes for container */
  className?: string
  /** Field content (input, textarea, select, etc.) */
  children: (fieldProps: {
    id: string
    labelId: string
    descriptionId: string | undefined
    errorId: string | undefined
    ariaDescribedBy: string | undefined
    hasError: boolean
  }) => ReactNode
}

/**
 * Form field wrapper with accessibility attributes
 *
 * @example
 * ```tsx
 * <FormField
 *   label="Question"
 *   description="Ask about the lecture content"
 *   error={error}
 *   required
 * >
 *   {({ id, labelId, descriptionId, errorId, ariaDescribedBy, hasError }) => (
 *     <input
 *       id={id}
 *       aria-labelledby={labelId}
 *       aria-describedby={ariaDescribedBy}
 *       aria-invalid={hasError}
 *       aria-errormessage={errorId}
 *       className={cn('input', hasError && 'border-danger')}
 *       {...props}
 *     />
 *   )}
 * </FormField>
 * ```
 */
export function FormField({
  label,
  id: customId,
  description,
  error,
  required,
  className,
  children,
}: FormFieldProps) {
  const id = customId ?? generateA11yId('field')
  const labelId = generateA11yId('label')
  const descriptionId = description ? generateA11yId('desc') : undefined
  const errorId = error ? generateA11yId('error') : undefined

  const ariaDescribedBy = [descriptionId, errorId].filter(Boolean).join(' ') || undefined
  const hasError = Boolean(error)

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {/* Label */}
      <label
        htmlFor={id}
        id={labelId}
        className="text-sm font-medium text-fg-primary"
      >
        {label}
        {required && (
          <span className="text-danger ml-1" aria-label="required">
            *
          </span>
        )}
      </label>

      {/* Field */}
      {children({
        id,
        labelId,
        descriptionId,
        errorId,
        ariaDescribedBy,
        hasError,
      })}

      {/* Description */}
      {description && (
        <p id={descriptionId} className="text-xs text-fg-secondary">
          {description}
        </p>
      )}

      {/* Error */}
      {error && (
        <p id={errorId} className="text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

/**
 * Text input with FormField wrapper
 */
export interface TextInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'aria-label'> {
  label: string
  description?: string
  error?: string
  /** Custom field ID (auto-generated if not provided) */
  fieldId?: string
  className?: string
}

export function TextInput({
  label,
  description,
  error,
  fieldId,
  className,
  ...props
}: TextInputProps) {
  return (
    <FormField
      label={label}
      id={fieldId}
      description={description}
      error={error}
      required={props.required}
      className={className}
    >
      {({ id, labelId, errorId, ariaDescribedBy, hasError }) => (
        <input
          id={id}
          type="text"
          aria-labelledby={labelId}
          aria-describedby={ariaDescribedBy}
          aria-invalid={hasError}
          aria-errormessage={errorId}
          className={cn('input', hasError && 'border-danger focus:outline-danger')}
          {...props}
        />
      )}
    </FormField>
  )
}

/**
 * Textarea with FormField wrapper
 */
export interface TextAreaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> {
  label: string
  description?: string
  error?: string
  /** Custom field ID (auto-generated if not provided) */
  fieldId?: string
  className?: string
}

export function TextArea({
  label,
  description,
  error,
  fieldId,
  className,
  ...props
}: TextAreaProps) {
  return (
    <FormField
      label={label}
      id={fieldId}
      description={description}
      error={error}
      required={props.required}
      className={className}
    >
      {({ id, labelId, errorId, ariaDescribedBy, hasError }) => (
        <textarea
          id={id}
          aria-labelledby={labelId}
          aria-describedby={ariaDescribedBy}
          aria-invalid={hasError}
          aria-errormessage={errorId}
          className={cn(
            'input',
            'min-h-24 resize-y',
            hasError && 'border-danger focus:outline-danger'
          )}
          {...props}
        />
      )}
    </FormField>
  )
}

/**
 * Select with FormField wrapper
 */
export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps extends Omit<React.HTMLAttributes<HTMLSelectElement>, 'id' | 'children' | 'required'> {
  label: string
  description?: string
  error?: string
  options: SelectOption[]
  /** Custom field ID (auto-generated if not provided) */
  fieldId?: string
  className?: string
  value?: string
  onValueChange?: (value: string) => void
  /** Whether the field is required */
  required?: boolean
}

export function Select({
  label,
  description,
  error,
  options,
  fieldId,
  className,
  value,
  onValueChange,
  ...props
}: SelectProps) {
  return (
    <FormField
      label={label}
      id={fieldId}
      description={description}
      error={error}
      required={props.required}
      className={className}
    >
      {({ id, labelId, errorId, ariaDescribedBy, hasError }) => (
        <select
          id={id}
          aria-labelledby={labelId}
          aria-describedby={ariaDescribedBy}
          aria-invalid={hasError}
          aria-errormessage={errorId}
          className={cn('input', hasError && 'border-danger focus:outline-danger')}
          value={value}
          onChange={(e) => onValueChange?.(e.target.value)}
          {...props}
        >
          {options.map((option) => (
            <option
              key={option.value}
              value={option.value}
              disabled={option.disabled}
            >
              {option.label}
            </option>
          ))}
        </select>
      )}
    </FormField>
  )
}

/**
 * Checkbox with label
 */
export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
  description?: string
  error?: string
  /** Custom field ID (auto-generated if not provided) */
  fieldId?: string
  className?: string
}

export function Checkbox({
  label,
  description,
  error,
  fieldId,
  className,
  ...props
}: CheckboxProps) {
  const id = fieldId ?? generateA11yId('checkbox')
  const descriptionId = description ? generateA11yId('desc') : undefined
  const errorId = error ? generateA11yId('error') : undefined
  const ariaDescribedBy = [descriptionId, errorId].filter(Boolean).join(' ') || undefined
  const hasError = Boolean(error)

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="flex items-start gap-2">
        <input
          id={id}
          type="checkbox"
          aria-describedby={ariaDescribedBy}
          aria-invalid={hasError}
          aria-errormessage={errorId}
          className={cn(
            'mt-0.5 w-4 h-4 rounded border-border',
            'text-accent focus:ring-2 focus:ring-accent focus:ring-offset-0',
            hasError && 'border-danger'
          )}
          {...props}
        />
        <div className="flex-1">
          <label
            htmlFor={id}
            className="text-sm font-medium text-fg-primary cursor-pointer"
          >
            {label}
          </label>
          {description && (
            <p id={descriptionId} className="text-xs text-fg-secondary mt-0.5">
              {description}
            </p>
          )}
        </div>
      </div>
      {error && (
        <p id={errorId} className="text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
