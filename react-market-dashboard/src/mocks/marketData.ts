import { DataMode, FinancialOverview, MarketActivity, PlayersResponse, QuickStats, SystemStatus, TopPerformer } from '../types'

const financialOverviewFallback: Record<DataMode, FinancialOverview> = {
  ecos: {
    total_market_value: 2450000000,
    active_contracts: 128,
    avg_brand_value: 1850000,
    market_activity: 92.4,
    athlete_count: 240,
  },
  nfl: {
    total_market_value: 3820000000,
    active_contracts: 164,
    avg_brand_value: 2120000,
    market_activity: 88.1,
    athlete_count: 320,
  },
}

const topPerformersFallback: Record<DataMode, TopPerformer[]> = {
  ecos: [
    { rank: 1, name: 'Avery Thompson', position: 'WR', team: 'SEA', brand_value: 7200000, change_pct: 6.4 },
    { rank: 2, name: 'Miles Carter', position: 'QB', team: 'KC', brand_value: 6850000, change_pct: 5.8 },
    { rank: 3, name: 'Jordan Ellis', position: 'RB', team: 'SF', brand_value: 6320000, change_pct: 4.7 },
    { rank: 4, name: 'Noah Reyes', position: 'TE', team: 'DAL', brand_value: 6010000, change_pct: 3.9 },
    { rank: 5, name: 'Jaden Brooks', position: 'WR', team: 'BUF', brand_value: 5740000, change_pct: 3.2 },
  ],
  nfl: [
    { rank: 1, name: 'Patrick Mahomes', position: 'QB', team: 'KC', brand_value: 8250000, change_pct: 7.1 },
    { rank: 2, name: 'Justin Jefferson', position: 'WR', team: 'MIN', brand_value: 7910000, change_pct: 6.3 },
    { rank: 3, name: 'Micah Parsons', position: 'LB', team: 'DAL', brand_value: 7560000, change_pct: 5.1 },
    { rank: 4, name: 'Christian McCaffrey', position: 'RB', team: 'SF', brand_value: 7120000, change_pct: 4.5 },
    { rank: 5, name: 'Jalen Hurts', position: 'QB', team: 'PHI', brand_value: 6880000, change_pct: 3.9 },
  ],
}

const marketActivityFallback: Record<DataMode, MarketActivity[]> = {
  ecos: [
    {
      time: '09:15',
      type: 'Brand Deal',
      tag_class: 'tag-endorsement',
      priority: 'High',
      description: 'Avery Thompson signs new apparel deal boosting off-field value.',
    },
    {
      time: '09:42',
      type: 'Performance',
      tag_class: 'tag-performance',
      priority: 'Medium',
      description: 'Miles Carter posts 4 TD performance with 320 passing yards.',
    },
    {
      time: '10:05',
      type: 'Contract',
      tag_class: 'tag-contract',
      priority: 'Medium',
      description: 'Jordan Ellis nearing extension; negotiations accelerated by agent.',
    },
    {
      time: '10:21',
      type: 'Social Buzz',
      tag_class: 'tag-social',
      priority: 'Low',
      description: 'Noah Reyes trends on social platforms after viral charity campaign.',
    },
    {
      time: '10:48',
      type: 'Trade Watch',
      tag_class: 'tag-trade',
      priority: 'Medium',
      description: 'Multiple teams monitoring Jaden Brooks for late-season push.',
    },
  ],
  nfl: [
    {
      time: '09:08',
      type: 'Contract',
      tag_class: 'tag-contract',
      priority: 'High',
      description: 'Kansas City finalizing restructured deal with Patrick Mahomes.',
    },
    {
      time: '09:37',
      type: 'Performance',
      tag_class: 'tag-performance',
      priority: 'High',
      description: 'Justin Jefferson clears 200 yards receiving in primetime win.',
    },
    {
      time: '09:59',
      type: 'Brand Deal',
      tag_class: 'tag-endorsement',
      priority: 'Medium',
      description: 'Micah Parsons secures national tech sponsorship through 2026.',
    },
    {
      time: '10:27',
      type: 'Health Update',
      tag_class: 'tag-performance',
      priority: 'Medium',
      description: 'Christian McCaffrey cleared for full participation after rest day.',
    },
    {
      time: '10:46',
      type: 'Social Buzz',
      tag_class: 'tag-social',
      priority: 'Low',
      description: 'Jalen Hurts launches fan engagement platform with record signups.',
    },
  ],
}

const quickStatsFallback: Record<DataMode, QuickStats> = {
  ecos: {
    teams_tracked: 32,
    data_points: '1.2M',
    update_freq: 'Every 6 min',
  },
  nfl: {
    teams_tracked: 32,
    data_points: '2.4M',
    update_freq: 'Every 3 min',
  },
}

const systemStatusFallback: SystemStatus = {
  api_status: 'Operational',
  data_freshness: 'Updated 4 minutes ago',
  sync_rate: '98.6% uptime',
}

const playersFallback: Record<DataMode, PlayersResponse> = {
  ecos: {
    mode: 'ecos',
    total: 12,
    players: [
      { name: 'Avery Thompson', position: 'WR', team: 'SEA', brand_value: 7200000, total_gravity: 91.2 },
      { name: 'Miles Carter', position: 'QB', team: 'KC', brand_value: 6850000, total_gravity: 89.5 },
      { name: 'Jordan Ellis', position: 'RB', team: 'SF', brand_value: 6320000, total_gravity: 87.1 },
      { name: 'Noah Reyes', position: 'TE', team: 'DAL', brand_value: 6010000, total_gravity: 84.6 },
      { name: 'Jaden Brooks', position: 'WR', team: 'BUF', brand_value: 5740000, total_gravity: 83.3 },
      { name: 'Landon Pierce', position: 'CB', team: 'NYJ', brand_value: 5460000, total_gravity: 82.5 },
      { name: 'Kellen Marsh', position: 'QB', team: 'DET', brand_value: 5280000, total_gravity: 81.7 },
      { name: 'Rowan Mitchell', position: 'LB', team: 'BAL', brand_value: 5120000, total_gravity: 80.9 },
      { name: 'Darius Cole', position: 'RB', team: 'MIA', brand_value: 4980000, total_gravity: 79.6 },
      { name: 'Caleb Monroe', position: 'WR', team: 'LAR', brand_value: 4860000, total_gravity: 78.8 },
      { name: 'Eli Navarro', position: 'S', team: 'GB', brand_value: 4720000, total_gravity: 77.9 },
      { name: 'Micah Sloan', position: 'TE', team: 'CHI', brand_value: 4630000, total_gravity: 77.1 },
    ],
  },
  nfl: {
    mode: 'nfl',
    total: 12,
    players: [
      { name: 'Patrick Mahomes', position: 'QB', team: 'KC', brand_value: 8250000, total_gravity: 94.3 },
      { name: 'Justin Jefferson', position: 'WR', team: 'MIN', brand_value: 7910000, total_gravity: 92.8 },
      { name: 'Micah Parsons', position: 'LB', team: 'DAL', brand_value: 7560000, total_gravity: 90.6 },
      { name: 'Christian McCaffrey', position: 'RB', team: 'SF', brand_value: 7120000, total_gravity: 89.2 },
      { name: 'Jalen Hurts', position: 'QB', team: 'PHI', brand_value: 6880000, total_gravity: 87.9 },
      { name: 'Tyreek Hill', position: 'WR', team: 'MIA', brand_value: 6640000, total_gravity: 86.1 },
      { name: 'T.J. Watt', position: 'LB', team: 'PIT', brand_value: 6410000, total_gravity: 85.4 },
      { name: 'Josh Allen', position: 'QB', team: 'BUF', brand_value: 6260000, total_gravity: 84.7 },
      { name: 'Sauce Gardner', position: 'CB', team: 'NYJ', brand_value: 5980000, total_gravity: 83.2 },
      { name: "Ja'Marr Chase", position: 'WR', team: 'CIN', brand_value: 5820000, total_gravity: 82.5 },
      { name: 'Nick Bosa', position: 'DE', team: 'SF', brand_value: 5710000, total_gravity: 81.9 },
      { name: 'Lamar Jackson', position: 'QB', team: 'BAL', brand_value: 5580000, total_gravity: 81.1 },
    ],
  },
}

const handleFallback = <T>(mode: DataMode, fallbackMap: Record<DataMode, T>): T => fallbackMap[mode]

export const getFallbackFinancialOverview = (mode: DataMode): FinancialOverview =>
  handleFallback(mode, financialOverviewFallback)

export const getFallbackTopPerformers = (mode: DataMode): TopPerformer[] =>
  handleFallback(mode, topPerformersFallback)

export const getFallbackMarketActivity = (mode: DataMode): MarketActivity[] =>
  handleFallback(mode, marketActivityFallback)

export const getFallbackQuickStats = (mode: DataMode): QuickStats =>
  handleFallback(mode, quickStatsFallback)

export const getFallbackSystemStatus = (): SystemStatus => systemStatusFallback

export const getFallbackPlayers = (mode: DataMode): PlayersResponse =>
  handleFallback(mode, playersFallback)
