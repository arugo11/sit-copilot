interface ToggleSwitchProps {
  checked: boolean
  onChange: () => void
  label?: string
  disabled?: boolean
}

export function ToggleSwitch({ checked, onChange, label, disabled = false }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={`
        relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full
        transition-colors duration-200 ease-in-out
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
        disabled:cursor-not-allowed disabled:opacity-50
        ${checked ? 'bg-accent' : 'bg-bg-muted'}
      `}
    >
      <span
        className={`
          pointer-events-none inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm ring-0
          transition-transform duration-200 ease-in-out
          ${checked ? 'translate-x-4' : 'translate-x-0.5'}
        `}
      />
    </button>
  )
}
