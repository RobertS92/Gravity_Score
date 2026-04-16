import { useEffect, useState } from 'react'
import { useRosterStore } from '../../stores/rosterStore'
import { getRoster, type RosterAthleteRow } from '../../api/roster'
import { WatchlistModal } from '../layout/WatchlistModal'
import styles from './RosterBuilderView.module.css'

const USD = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function fmtUsd(n: number | null | undefined) {
  if (!n) return '—'
  return USD.format(n)
}

function valueLabelClass(label: string) {
  if (label === 'DEAL') return styles.labelDeal
  if (label === 'PREMIUM') return styles.labelPremium
  return styles.labelFair
}

function gradeColor(grade: string) {
  if (grade.startsWith('A')) return '#00ff88'
  if (grade.startsWith('B')) return '#7af0a0'
  if (grade.startsWith('C')) return '#f0c844'
  if (grade.startsWith('D')) return '#f07a44'
  return '#ff4444'
}

function effColor(score: number) {
  if (score >= 70) return '#00ff88'
  if (score >= 50) return '#f0c844'
  return '#ff4444'
}

function BudgetBar({ spent, budget }: { spent: number; budget: number }) {
  const pct = budget > 0 ? Math.min(100, (spent / budget) * 100) : 0
  const over = spent > budget
  return (
    <div className={styles.budgetBarWrap}>
      <div className={styles.budgetBarLabel}>
        <span>
          <span className={over ? styles.budgetOver : styles.budgetOk}>{fmtUsd(spent)}</span>
          {' spent of '}
          <span>{fmtUsd(budget)}</span>
        </span>
        {over && <span className={styles.overBudgetTag}>OVER BUDGET</span>}
        {!over && (
          <span className={styles.budgetRemain}>{fmtUsd(budget - spent)} remaining</span>
        )}
      </div>
      <div className={styles.budgetTrack}>
        <div
          className={over ? styles.budgetFillOver : styles.budgetFill}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function PositionDepth({ depth }: { depth: Record<string, number> }) {
  const entries = Object.entries(depth).sort((a, b) => b[1] - a[1])
  return (
    <div className={styles.posDepth}>
      {entries.map(([pos, count]) => (
        <div key={pos} className={styles.posRow}>
          <span className={styles.posLabel}>{pos}</span>
          <span className={styles.posCount}>{count}</span>
        </div>
      ))}
    </div>
  )
}

export function RosterBuilderView() {
  const {
    name, budget_usd, slots, scored,
    isSaving, isScoring, error,
    savedRosters, isLoadingSaved,
    setName, setBudget,
    removeSlot, setCostOverride,
    saveCurrentRoster, loadSavedRosters, deleteSavedRoster,
    loadRosterById, reset,
  } = useRosterStore()

  const [showPlayerModal, setShowPlayerModal] = useState(false)
  const [showSaved, setShowSaved] = useState(false)
  const [editingCost, setEditingCost] = useState<string | null>(null)
  const [costDraft, setCostDraft] = useState('')

  useEffect(() => {
    void loadSavedRosters()
  }, [loadSavedRosters])

  const athletes: RosterAthleteRow[] = scored?.athletes ?? []

  const handleSave = () => void saveCurrentRoster()

  const handleLoadRoster = (id: string) => {
    const summary = savedRosters.find((r) => r.id === id)
    if (!summary) return
    getRoster(id).then((data) => {
      loadRosterById(data)
      setShowSaved(false)
    })
  }

  const startEditCost = (athleteId: string, current: number) => {
    setEditingCost(athleteId)
    setCostDraft(String(Math.round(current)))
  }

  const commitCost = (athleteId: string) => {
    const val = parseFloat(costDraft.replace(/[^0-9.]/g, ''))
    if (!isNaN(val) && val >= 0) {
      setCostOverride(athleteId, val)
    }
    setEditingCost(null)
  }

  return (
    <div className={styles.page}>
      {/* LEFT — Config */}
      <aside className={styles.leftPanel}>
        <div className={styles.panelTitle}>ROSTER CONFIG</div>

        <label className={styles.fieldLabel}>ROSTER NAME</label>
        <input
          className={styles.textInput}
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
        />

        <label className={styles.fieldLabel}>BUDGET</label>
        <div className={styles.budgetInputRow}>
          <span className={styles.currencySymbol}>$</span>
          <input
            className={styles.numberInput}
            type="number"
            min={0}
            max={10_000_000}
            step={50_000}
            value={budget_usd}
            onChange={(e) => setBudget(Number(e.target.value))}
          />
        </div>
        <input
          type="range"
          className={styles.slider}
          min={0}
          max={10_000_000}
          step={50_000}
          value={budget_usd}
          onChange={(e) => setBudget(Number(e.target.value))}
        />
        <div className={styles.sliderLabels}>
          <span>$0</span><span>$10M</span>
        </div>

        <div className={styles.actionRow}>
          <button
            type="button"
            className={styles.saveBtn}
            onClick={handleSave}
            disabled={isSaving || slots.length === 0}
          >
            {isSaving ? 'SAVING…' : 'SAVE ROSTER'}
          </button>
          <button
            type="button"
            className={styles.resetBtn}
            onClick={reset}
          >
            NEW
          </button>
        </div>

        <button
          type="button"
          className={styles.savedRostersBtn}
          onClick={() => setShowSaved((v) => !v)}
        >
          {showSaved ? '▲ HIDE SAVED' : '▼ SAVED ROSTERS'}
        </button>

        {showSaved && (
          <div className={styles.savedList}>
            {isLoadingSaved && <div className={styles.dimText}>Loading…</div>}
            {!isLoadingSaved && savedRosters.length === 0 && (
              <div className={styles.dimText}>No saved rosters</div>
            )}
            {savedRosters.map((r) => (
              <div key={r.id} className={styles.savedRow}>
                <button
                  type="button"
                  className={styles.savedLoadBtn}
                  onClick={() => handleLoadRoster(r.id)}
                >
                  {r.name}
                  <span className={styles.savedMeta}>{r.slot_count} players</span>
                </button>
                <button
                  type="button"
                  className={styles.deleteRosterBtn}
                  onClick={() => void deleteSavedRoster(r.id)}
                  title="Delete roster"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {error && <div className={styles.errorMsg}>{error}</div>}
      </aside>

      {/* CENTER — Roster Table */}
      <main className={styles.center}>
        <div className={styles.centerHeader}>
          <div className={styles.panelTitle}>{name || 'MY ROSTER'}</div>
          <button
            type="button"
            className={styles.addPlayerBtn}
            onClick={() => setShowPlayerModal(true)}
          >
            + ADD PLAYER
          </button>
        </div>

        <BudgetBar spent={scored?.total_spend ?? 0} budget={budget_usd} />

        {isScoring && <div className={styles.scoringMsg}>Scoring roster…</div>}

        {athletes.length === 0 && !isScoring && (
          <div className={styles.emptyRoster}>
            <div className={styles.emptyIcon}>◈</div>
            <div className={styles.emptyTitle}>No players yet</div>
            <div className={styles.emptyHint}>Click + ADD PLAYER to build your roster</div>
          </div>
        )}

        {athletes.length > 0 && (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>PLAYER</th>
                  <th>POS</th>
                  <th>SCHOOL</th>
                  <th>PROOF</th>
                  <th>NIL COST</th>
                  <th>VALUE</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {athletes.map((a) => (
                  <tr key={a.athlete_id}>
                    <td className={styles.nameCell}>{a.name}</td>
                    <td className={styles.posCell}>{a.position || '—'}</td>
                    <td className={styles.schoolCell}>{a.school || '—'}</td>
                    <td className={styles.proofCell}>
                      <span
                        className={styles.proofScore}
                        style={{ color: a.proof_score >= 70 ? '#00ff88' : a.proof_score >= 50 ? '#f0c844' : '#f07a44' }}
                      >
                        {a.proof_score?.toFixed(1) ?? '—'}
                      </span>
                    </td>
                    <td className={styles.costCell}>
                      {editingCost === a.athlete_id ? (
                        <input
                          autoFocus
                          className={styles.costInput}
                          value={costDraft}
                          onChange={(e) => setCostDraft(e.target.value)}
                          onBlur={() => commitCost(a.athlete_id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') commitCost(a.athlete_id)
                            if (e.key === 'Escape') setEditingCost(null)
                          }}
                        />
                      ) : (
                        <button
                          type="button"
                          className={styles.costBtn}
                          onClick={() => startEditCost(a.athlete_id, a.nil_cost)}
                          title="Click to override NIL cost"
                        >
                          {fmtUsd(a.nil_cost)}
                          {a.nil_cost_override != null && <span className={styles.overrideBadge}>*</span>}
                        </button>
                      )}
                    </td>
                    <td>
                      <span className={`${styles.valueLabel} ${valueLabelClass(a.value_label)}`}>
                        {a.value_label}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className={styles.removeSlotBtn}
                        onClick={() => removeSlot(a.athlete_id)}
                        title="Remove from roster"
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {/* RIGHT — Team Grades */}
      <aside className={styles.rightPanel}>
        <div className={styles.panelTitle}>TEAM GRADES</div>

        {!scored && (
          <div className={styles.dimText}>Add players to see grades</div>
        )}

        {scored && (
          <>
            <div className={styles.gradeCard}>
              <div className={styles.gradeLabel}>TALENT GRADE</div>
              <div
                className={styles.gradeValue}
                style={{ color: gradeColor(scored.talent_grade) }}
              >
                {scored.talent_grade}
              </div>
              <div className={styles.gradeSub}>avg proof {scored.avg_proof.toFixed(1)}</div>
            </div>

            <div className={styles.gradeCard}>
              <div className={styles.gradeLabel}>EFFICIENCY SCORE</div>
              <div
                className={styles.gradeValue}
                style={{ color: effColor(scored.efficiency_score) }}
              >
                {scored.efficiency_score.toFixed(0)}
                <span className={styles.gradeUnit}>/100</span>
              </div>
              <div className={styles.gradeSub}>proof-per-dollar</div>
            </div>

            <div className={styles.gradeCard}>
              <div className={styles.gradeLabel}>TOTAL SPEND</div>
              <div className={styles.gradeValueMid}>{fmtUsd(scored.total_spend)}</div>
              <div className={styles.gradeSub}>
                {budget_usd > 0
                  ? `${Math.min(100, Math.round((scored.total_spend / budget_usd) * 100))}% of budget`
                  : '—'}
              </div>
            </div>

            <div className={styles.gradeCard}>
              <div className={styles.gradeLabel}>ROSTER DEPTH</div>
              <PositionDepth depth={scored.position_depth} />
            </div>

            <div className={styles.gradeCard}>
              <div className={styles.gradeLabel}>VALUE BREAKDOWN</div>
              <div className={styles.valueBreakdown}>
                {['DEAL', 'FAIR', 'PREMIUM', 'UNPRICED'].map((lbl) => {
                  const count = scored.athletes.filter((a) => a.value_label === lbl).length
                  if (!count) return null
                  return (
                    <div key={lbl} className={styles.valueBkRow}>
                      <span className={`${styles.valueLabel} ${valueLabelClass(lbl)}`}>{lbl}</span>
                      <span className={styles.valueBkCount}>{count}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </>
        )}
      </aside>

      {showPlayerModal && (
        <WatchlistModal
          mode="roster"
          onClose={() => setShowPlayerModal(false)}
        />
      )}
    </div>
  )
}
