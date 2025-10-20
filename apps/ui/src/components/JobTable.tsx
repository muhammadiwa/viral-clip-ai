import type { Job } from '../types'

interface JobTableProps {
  jobs: Job[]
}

const jobLabels: Record<string, string> = {
  ingest: 'Ingest',
  transcode: 'Transcode',
  transcription: 'Transcription',
  alignment: 'Alignment',
  clip_discovery: 'Clip discovery',
  subtitle_render: 'Subtitle styling',
  tts_render: 'Voice-over',
  project_export: 'Project export',
  movie_retell: 'Movie retell',
}

const statusLabels: Record<string, string> = {
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Succeeded',
  failed: 'Failed',
  paused: 'Paused',
  cancelled: 'Cancelled',
}

export function JobTable({ jobs }: JobTableProps) {
  if (jobs.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 bg-slate-900/40 p-4 text-sm text-slate-400">
        No jobs have run for this project yet.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full divide-y divide-white/10 text-sm">
        <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-4 py-3 text-left">Job</th>
            <th className="px-4 py-3 text-left">Status</th>
            <th className="px-4 py-3 text-left">Progress</th>
            <th className="px-4 py-3 text-left">Updated</th>
            <th className="px-4 py-3 text-left">Message</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 bg-slate-950/50">
          {jobs.map((job) => (
            <tr key={job.id} className="hover:bg-white/5">
              <td className="px-4 py-3 font-medium text-white">
                {jobLabels[job.job_type] ?? job.job_type}
              </td>
              <td className="px-4 py-3 text-slate-200">
                {statusLabels[job.status] ?? job.status}
              </td>
              <td className="px-4 py-3 text-slate-200">{Math.round(job.progress * 100)}%</td>
              <td className="px-4 py-3 text-slate-400">
                {new Date(job.updated_at).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-slate-300">
                {job.message ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
