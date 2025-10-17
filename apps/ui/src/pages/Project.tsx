
import { useParams } from 'react-router-dom'
export default function Project(){
  const { id } = useParams()
  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-semibold">Project {id}</h1>
      <div className="card">Timeline / Clips / Subtitles / Dubbing / Export</div>
    </div>
  )
}
