interface AchievementCardProps {
  title: string
  description: string
  icon: string
  unlocked: boolean
  unlocked_at?: string | null
}

export default function AchievementCard({ title, description, icon, unlocked, unlocked_at }: AchievementCardProps) {
  return (
    <div className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${
      unlocked
        ? 'border-violet-700 bg-violet-900/20'
        : 'border-[#2a2a3a] bg-[#111118] opacity-50'
    }`}>
      <span className="text-2xl shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${unlocked ? 'text-white' : 'text-gray-400'}`}>{title}</p>
        <p className="text-xs text-gray-500 mt-0.5">{description}</p>
        {unlocked && unlocked_at && (
          <p className="text-xs text-violet-400 mt-1">
            Unlocked {new Date(unlocked_at).toLocaleDateString()}
          </p>
        )}
      </div>
      {unlocked && (
        <span className="text-violet-400 shrink-0">✓</span>
      )}
    </div>
  )
}
