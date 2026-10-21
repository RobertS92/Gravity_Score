/**
 * Profile `org_name` is a free-text preference label.
 * CapIQ membership is the FK `organization_id` from /auth/me.
 * These are intentionally separate — Settings must never imply they are the same.
 */

export type OrgAccessSnapshot = {
  organizationId: string | null
  organizationName: string | null
  organizationSlug: string | null
  role: string | null
  profileOrgName: string | null
  orgType: string | null
}

export function formatAccountRole(role: string | null | undefined): string {
  switch ((role ?? '').trim()) {
    case 'admin':
      return 'Platform admin'
    case 'school_admin':
      return 'School admin'
    case 'school_coach':
      return 'School coach'
    case 'agent':
      return 'Agent'
    case 'brand':
      return 'Brand'
    case '':
      return 'Not set'
    default:
      return role!.replace(/_/g, ' ')
  }
}

/** CapIQ surfaces available once `organization_id` is linked. */
export function capiqFeaturesForMembership(hasOrg: boolean, role: string | null | undefined): string[] {
  if (!hasOrg) {
    return [
      'Cap utilization and roster (locked until an organization is linked)',
      'Scenarios, outlook, and approvals (locked)',
      'School data submissions and alerts (locked)',
    ]
  }
  const base = [
    'Roster cap utilization and contracts',
    'Scenarios and five-year outlook',
    'Approvals workflow and deal desk',
    'Cap alerts and cash-flow views',
  ]
  if (role === 'admin' || role === 'school_admin') {
    return [...base, 'Multi-sport rollup, allocation, and audit log']
  }
  if (role === 'school_coach') {
    return [...base.filter((f) => !f.startsWith('Approvals')), 'Sport-scoped coach views']
  }
  return base
}

export function resolveMissingOrgAccessSteps(snapshot: Pick<OrgAccessSnapshot, 'organizationId' | 'orgType' | 'profileOrgName'>): string[] {
  if (snapshot.organizationId) {
    return [
      'Your account is linked to a CapIQ organization. Open CapIQ from the sidebar to use roster and budget tools.',
    ]
  }
  const schoolLike = snapshot.orgType === 'school' || snapshot.orgType === 'nil_collective'
  const steps: string[] = []
  if (schoolLike) {
    steps.push(
      'Re-run onboarding as School / Athletic Department or NIL Collective and enter the exact organization name so Gravity can create or attach the org record.',
    )
  } else if (snapshot.orgType) {
    steps.push(
      'CapIQ is for school and NIL collective accounts. Your profile type does not create CapIQ membership from the organization label alone.',
    )
  } else {
    steps.push('Complete onboarding and choose School / Athletic Department or NIL Collective with an organization name.')
  }
  if (snapshot.profileOrgName?.trim()) {
    steps.push(
      `“${snapshot.profileOrgName.trim()}” under Settings is only a profile label — it does not grant CapIQ access by itself.`,
    )
  }
  steps.push('Or ask a school admin to add your user to their organization in CapIQ.')
  return steps
}

export function membershipStatusLabel(hasOrg: boolean): string {
  return hasOrg ? 'Linked' : 'Not linked'
}

/** Pure helper for Cap rail dollars (API uses cents). */
export function centsToDollars(cents: number | null | undefined): number | null {
  if (cents == null || !Number.isFinite(cents)) return null
  return cents / 100
}

/**
 * Demo-only figures formerly hard-coded in the Cap right rail.
 * Kept for tests / explicit SAMPLE UI — never present as live school data.
 */
export const ILLUSTRATIVE_CAP_FIGURES = {
  totalBudgetDollars: 15_000_000,
  committedDollars: 11_240_000,
  headroomDollars: 3_760_000,
  utilizationPct: 75,
} as const

export function sampleCapFigureLabel(kind: 'budget' | 'committed' | 'headroom'): string {
  switch (kind) {
    case 'budget':
      return 'SAMPLE — illustrative budget (not your school)'
    case 'committed':
      return 'SAMPLE — illustrative committed (not your school)'
    case 'headroom':
      return 'SAMPLE — illustrative headroom (not your school)'
  }
}
