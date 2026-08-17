import type { DiagramSpec } from '../../api'
import BoardDiagram from './BoardDiagram'
import DiagramFrame from './DiagramFrame'
import GeometryDiagram from './GeometryDiagram'
import GraphDiagram from './GraphDiagram'
import PlotDiagram from './PlotDiagram'
import { useDiagramSteps } from './useDiagramSteps'

/**
 * Renders one diagram spec.
 *
 * An unrecognised kind renders nothing rather than throwing. The backend can
 * learn a fifth kind before a cached client build knows about it, and a lesson
 * losing one figure is a far better outcome than a lesson losing its page.
 */
export default function Diagram({ spec }: { spec: DiagramSpec }) {
  const steps = useDiagramSteps(spec.steps ?? [])

  const body = (() => {
    switch (spec.kind) {
      case 'board':
        return <BoardDiagram spec={spec} steps={steps} />
      case 'graph':
        return <GraphDiagram spec={spec} steps={steps} />
      case 'plot':
        return <PlotDiagram spec={spec} steps={steps} />
      case 'geometry':
        return <GeometryDiagram spec={spec} steps={steps} />
      default:
        return null
    }
  })()

  if (body === null) return null

  return (
    <DiagramFrame title={spec.title} caption={spec.caption} steps={steps}>
      {body}
    </DiagramFrame>
  )
}
