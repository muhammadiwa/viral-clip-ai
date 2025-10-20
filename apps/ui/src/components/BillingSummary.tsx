import { useQuery } from '@tanstack/react-query'
import { useApi } from '../hooks/useApi'
import { useOrg } from '../contexts/OrgContext'
import type { SubscriptionResponse, UsageResponse } from '../types'

export function BillingSummary() {
  const { orgId } = useOrg()
  const { request } = useApi()

  const subscriptionQuery = useQuery({
    queryKey: ['billing', 'subscription', orgId],
    enabled: !!orgId,
    queryFn: () => request<SubscriptionResponse>('/v1/billing/subscription'),
  })

  const usageQuery = useQuery({
    queryKey: ['billing', 'usage', orgId],
    enabled: !!orgId,
    queryFn: () => request<UsageResponse>('/v1/billing/usage'),
  })

  if (!orgId) {
    return null
  }

  if (subscriptionQuery.isLoading || usageQuery.isLoading) {
    return (
      <section className="rounded-2xl border border-white/10 bg-slate-900/60 p-5 text-sm text-slate-300">
        Loading subscription details…
      </section>
    )
  }

  if (subscriptionQuery.isError || usageQuery.isError || !subscriptionQuery.data || !usageQuery.data) {
    return (
      <section className="rounded-2xl border border-rose-500/40 bg-rose-900/40 p-5 text-sm text-rose-100">
        Unable to load billing details for this organization.
      </section>
    )
  }

  const subscription = subscriptionQuery.data.data
  const usage = usageQuery.data.data

  const limits = [
    {
      label: 'Minutes processed',
      value: usage.minutes_processed,
      quota: subscription.minutes_quota,
      unit: 'min',
    },
    {
      label: 'Clips generated',
      value: usage.clips_generated,
      quota: subscription.clip_quota,
      unit: 'clips',
    },
    {
      label: 'Movie retells',
      value: usage.retells_created,
      quota: subscription.retell_quota,
      unit: 'retells',
    },
    {
      label: 'Storage consumed',
      value: usage.storage_gb,
      quota: subscription.storage_quota_gb,
      unit: 'GB',
    },
  ]

  return (
    <section className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Billing & quotas</h2>
          <p className="text-sm text-slate-400">
            {subscription.plan.toUpperCase()} plan · {subscription.status.replace(/_/g, ' ')} · {subscription.seats}{' '}
            seats
          </p>
        </div>
        {subscription.renews_at && (
          <span className="text-xs text-slate-400">
            Renews {new Date(subscription.renews_at).toLocaleDateString()}
          </span>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {limits.map((entry) => {
          const percent = entry.quota ? Math.min(100, Math.round((entry.value / entry.quota) * 100)) : null
          return (
            <div key={entry.label} className="space-y-2 rounded-xl border border-white/5 bg-slate-950/60 p-4">
              <div className="flex items-center justify-between text-xs text-slate-300">
                <span className="font-semibold uppercase tracking-wide">{entry.label}</span>
                <span>
                  {entry.value.toLocaleString()} {entry.unit}
                  {entry.quota ? ` / ${entry.quota.toLocaleString()} ${entry.unit}` : ''}
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-800">
                <div
                  className="h-2 rounded-full bg-indigo-500 transition-all"
                  style={{ width: `${percent ?? 100}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
