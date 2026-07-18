import { Link, Route, Routes } from 'react-router-dom'
import GoalInputPage from './pages/GoalInputPage'
import CourseViewPage from './pages/CourseViewPage'
import ReviewSessionPage from './pages/ReviewSessionPage'
import PronunciationDrill from './pages/PronunciationDrill'

function App() {
  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <nav className="border-b border-[#2a2a3a] bg-[#111118] px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center gap-6">
          <Link to="/" className="text-lg font-semibold text-white">
            SuperLearned
          </Link>
          <Link to="/" className="text-sm text-gray-400 hover:text-white">
            New course
          </Link>
          <Link to="/review" className="text-sm text-gray-400 hover:text-white">
            Review
          </Link>
          <Link to="/pronunciation" className="text-sm text-gray-400 hover:text-white">
            Pronunciation
          </Link>
        </div>
      </nav>
      <main className="mx-auto max-w-3xl px-6 py-8">
        <Routes>
          <Route path="/" element={<GoalInputPage />} />
          <Route path="/courses/:courseId" element={<CourseViewPage />} />
          <Route path="/review" element={<ReviewSessionPage />} />
          <Route path="/pronunciation" element={<PronunciationDrill />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
