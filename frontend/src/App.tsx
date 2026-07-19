import { Link, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import CourseLibrary from './pages/CourseLibrary'
import CourseHome from './pages/CourseHome'
import LessonView from './pages/LessonView'
import ReviewSession from './pages/ReviewSession'
import PronunciationDrill from './pages/PronunciationDrill'

function App() {
  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <nav className="border-b border-[#2a2a3a] bg-[#111118] px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center gap-6">
          <Link to="/" className="text-lg font-semibold text-white">
            SuperLearned
          </Link>
          <Link to="/courses" className="text-sm text-gray-400 hover:text-white">
            Courses
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
          <Route path="/" element={<Home />} />
          <Route path="/courses" element={<CourseLibrary />} />
          <Route path="/courses/:courseId" element={<CourseHome />} />
          <Route path="/courses/:courseId/lessons/:lessonId" element={<LessonView />} />
          <Route path="/courses/:courseId/review" element={<ReviewSession />} />
          <Route path="/review" element={<ReviewSession />} />
          <Route path="/pronunciation" element={<PronunciationDrill />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
