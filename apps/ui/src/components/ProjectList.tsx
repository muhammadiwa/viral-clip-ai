import { Link } from 'react-router-dom'
import type { Project } from '../types'

interface ProjectListProps {
  projects: Project[]
}

export function ProjectList({ projects }: ProjectListProps) {
  if (projects.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 bg-slate-900/40 p-6 text-center text-sm text-slate-400">
        No projects yet. Create one to start processing videos.
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {projects.map((project) => (
        <Link
          key={project.id}
          to={`/projects/${project.id}`}
          className="group rounded-2xl border border-white/5 bg-slate-900/70 p-5 transition hover:border-indigo-400/60 hover:bg-slate-900"
        >
          <div className="flex items-start justify-between">
            <h3 className="text-lg font-semibold text-white group-hover:text-indigo-200">
              {project.name}
            </h3>
            <span className="rounded-full bg-indigo-500/20 px-2 py-1 text-xs text-indigo-200">
              {project.status.replace(/_/g, ' ')}
            </span>
          </div>
          {project.description && (
            <p className="mt-2 line-clamp-2 text-sm text-slate-300">{project.description}</p>
          )}
          <dl className="mt-4 flex flex-wrap gap-4 text-xs text-slate-400">
            <div>
              <dt className="uppercase tracking-wide">Created</dt>
              <dd>{new Date(project.created_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide">Export status</dt>
              <dd>{project.export_status.replace(/_/g, ' ')}</dd>
            </div>
          </dl>
        </Link>
      ))}
    </div>
  )
}
