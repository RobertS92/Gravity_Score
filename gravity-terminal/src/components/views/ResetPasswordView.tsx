import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { resetPassword } from '../../api/auth'
import styles from './LoginView.module.css'

export function ResetPasswordView() {
  const [search] = useSearchParams()
  const token = useMemo(() => search.get('token')?.trim() ?? '', [search])
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) {
      setError('Reset token is missing or invalid.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await resetPassword(token, password)
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reset password.')
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
        <p className={styles.sub}>SET NEW PASSWORD</p>
        {done ? (
          <>
            <p className={styles.sub}>Password updated. You can sign in now.</p>
            <p className={styles.signupHint}>
              Go to <Link to="/login" className={styles.signupLink}>Sign in</Link>
            </p>
          </>
        ) : (
          <form onSubmit={onSubmit} className={styles.form} noValidate>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="password">NEW PASSWORD</label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                className={styles.input}
                value={password}
                onChange={(e) => {
                  setError(null)
                  setPassword(e.target.value)
                }}
                disabled={loading}
                placeholder="At least 8 characters"
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="confirm">CONFIRM PASSWORD</label>
              <input
                id="confirm"
                type="password"
                autoComplete="new-password"
                className={styles.input}
                value={confirm}
                onChange={(e) => {
                  setError(null)
                  setConfirm(e.target.value)
                }}
                disabled={loading}
                placeholder="Repeat password"
              />
            </div>
            {error && <p className={styles.error}>{error}</p>}
            <button type="submit" className={styles.btn} disabled={loading}>
              {loading ? 'UPDATING...' : 'UPDATE PASSWORD'}
            </button>
          </form>
        )}
        <p className={styles.signupHint}>
          Back to <Link to="/login" className={styles.signupLink}>Sign in</Link>
        </p>
      </div>
    </div>
  )
}
