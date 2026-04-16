import type { ReactNode } from 'react'
import styles from './ActionButton.module.css'

export function ActionButton({
  children,
  variant = 'secondary',
  onClick,
  type = 'button',
  disabled = false,
}: {
  children: ReactNode
  variant?: 'primary' | 'secondary'
  onClick?: () => void
  type?: 'button' | 'submit'
  disabled?: boolean
}) {
  return (
    <button
      type={type}
      className={`${styles.btn} ${variant === 'primary' ? styles.primary : ''}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}
