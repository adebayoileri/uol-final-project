interface MasteryBarProps {
  name: string
  mastery: number  // 0.0–1.0
}

export default function MasteryBar({ name, mastery }: MasteryBarProps) {
  const pct = Math.round(mastery * 100)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-400 truncate max-w-[70%]">{name}</span>
        <span className="text-violet-400 font-mono tabular-nums">{pct}%</span>
      </div>
      <div className="h-1.5 bg-[#1a1a24] rounded-full overflow-hidden">
        <div
          className="h-full bg-violet-600 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
