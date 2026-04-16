import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { loginWithEmail } from '../../api/auth'
import { setSessionToken } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import styles from './LoginView.module.css'

export function LoginView() {
  const navigate = useNavigate()
  const hydrate = useAuthStore((s) => s.hydrate)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password.trim()) {
      setError('Email and password are required.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await loginWithEmail(email, password)
      setSessionToken(res.access_token)
      await hydrate()
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Check credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.logo}>GRAVITY</div>
        <p className={styles.sub}>NIL COMMERCIAL INTELLIGENCE</p>
        <form onSubmit={onSubmit} className={styles.form} noValidate>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="email">EMAIL</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className={styles.input}
              value={email}
              onChange={(e) => { setError(null); setEmail(e.target.value) }}
              disabled={loading}
              placeholder="agent@firm.com"
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="password">PASSWORD</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className={styles.input}
              value={password}
              onChange={(e) => { setError(null); setPassword(e.target.value) }}
              disabled={loading}
              placeholder="••••••••"
            />
          </div>
          {error && <p className={styles.error}>{error}</p>}
          <button type="submit" className={styles.btn} disabled={loading}>
            {loading ? 'AUTHENTICATING...' : 'SIGN IN'}
          </button>
        </form>
        <p className={styles.footer}>POWER 5 CFB · NCAAB MENS ONLY</p>
      </div>
    </div>
  )
}
