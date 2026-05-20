import { useState } from 'react'
import { Link } from 'react-router-dom'
import { forgotPassword } from '../../api/auth'
import styles from './LoginView.module.css'

export function ForgotPasswordView() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [doneMessage, setDoneMessage] = useState<string | null>(null)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) {
      setError('Email is required.')
      return
    }
    setLoading(true)
    setError(null)
    setDoneMessage(null)
    try {
      const res = await forgotPassword(email)
      setDoneMessage(res.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to submit password reset request.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <span>GRAVITY</span>
        </div>
        <p className={styles.sub}>RESET PASSWORD</p>
        <form onSubmit={onSubmit} className={styles.form} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="email">EMAIL</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className={styles.input}
              value={email}
              onChange={(e) => {
                setError(null)
                setDoneMessage(null)
                setEmail(e.target.value)
              }}
              disabled={loading}
              placeholder="agent@firm.com"
            />
          </div>
          {error && <p className={styles.error}>{error}</p>}
          {doneMessage && <p className={styles.sub}>{doneMessage}</p>}
          <button type="submit" className={styles.btn} disabled={loading}>
            {loading ? 'SENDING...' : 'SEND RESET LINK'}
          </button>
        </form>
        <p className={styles.signupHint}>
          Back to <Link to="/login" className={styles.signupLink}>Sign in</Link>
        </p>
      </div>
    </div>
  )
}
