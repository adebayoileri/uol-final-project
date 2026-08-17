import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Container, { type ContainerWidth } from './components/layout/Container'
import TopNav from './components/layout/TopNav'
import Footer from './components/layout/Footer'
import ErrorBoundary from './components/layout/ErrorBoundary'
import PageTransition from './motion/PageTransition'
import Home from './pages/Home'
import CourseLibrary from './pages/CourseLibrary'
import CourseHome from './pages/CourseHome'
import LessonView from './pages/LessonView'
import ReviewSession from './pages/ReviewSession'
import ReviewHub from './pages/ReviewHub'
import PronunciationDrill from './pages/PronunciationDrill'
import PracticeHub from './pages/PracticeHub'
import CourseDrills from './pages/CourseDrills'
import McqDrill from './pages/drills/McqDrill'
import MatchDrill from './pages/drills/MatchDrill'
import OrderDrill from './pages/drills/OrderDrill'
import ListenDrill from './pages/drills/ListenDrill'
import CompletionScreen from './pages/CompletionScreen'
import CourseTimeline from './pages/CourseTimeline'
import NotFound from './pages/NotFound'
import KitchenSink from './pages/KitchenSink'
import Login from './pages/Login'
import RequireAuth from './auth/RequireAuth'

/** Each route picks the container width that suits its content. */
function Page({ width, children }: { width: ContainerWidth; children: React.ReactNode }) {
  return (
    <Container width={width} className="py-8 sm:py-10">
      {children}
    </Container>
  )
}

function App() {
  const location = useLocation()
  // Only a running session is a focus surface. The hub at /review is a
  // browsing surface and keeps its footer.
  const focusMode =
    location.pathname === '/login' ||
    location.pathname === '/register' ||
    location.pathname === '/review/session' ||
    /^\/courses\/[^/]+\/review$/.test(location.pathname)

  return (
    <div className="bg-canvas flex min-h-dvh flex-col">
      <a
        href="#main"
        className="bg-brand-500 text-callout sr-only rounded-md px-4 py-2 font-medium text-white focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-60"
      >
        Skip to content
      </a>

      <TopNav />

      <main id="main" className="flex-1">
        <ErrorBoundary key={location.pathname}>
          <PageTransition>
            <Routes location={location}>
              {/* Public. Everything else sits under the guard below. */}
              <Route
                path="/login"
                element={
                  <Page width="medium">
                    <Login mode="login" />
                  </Page>
                }
              />
              <Route
                path="/register"
                element={
                  <Page width="medium">
                    <Login mode="register" />
                  </Page>
                }
              />

              {/* Pathless layout route: one insertion guards all 18 pages. */}
              <Route element={<RequireAuth />}>
              <Route
                path="/"
                element={
                  <Page width="wide">
                    <Home />
                  </Page>
                }
              />
              <Route
                path="/courses"
                element={
                  <Page width="wide">
                    <CourseLibrary />
                  </Page>
                }
              />
              <Route
                path="/courses/:courseId"
                element={
                  <Page width="wide">
                    <CourseHome />
                  </Page>
                }
              />
              <Route
                path="/courses/:courseId/lessons/:lessonId"
                element={
                  <Page width="full">
                    <LessonView />
                  </Page>
                }
              />
              <Route
                path="/courses/:courseId/review"
                element={
                  <Page width="wide">
                    <ReviewSession />
                  </Page>
                }
              />
              <Route
                path="/review"
                element={
                  <Page width="wide">
                    <ReviewHub />
                  </Page>
                }
              />
              <Route
                path="/review/session"
                element={
                  <Page width="wide">
                    <ReviewSession />
                  </Page>
                }
              />
              <Route
                path="/practice"
                element={
                  <Page width="wide">
                    <PracticeHub />
                  </Page>
                }
              />
              <Route
                path="/practice/:courseId"
                element={
                  <Page width="wide">
                    <CourseDrills />
                  </Page>
                }
              />
              <Route
                path="/practice/:courseId/mcq"
                element={
                  <Page width="medium">
                    <McqDrill />
                  </Page>
                }
              />
              <Route
                path="/practice/:courseId/match"
                element={
                  <Page width="medium">
                    <MatchDrill />
                  </Page>
                }
              />
              <Route
                path="/practice/:courseId/order"
                element={
                  <Page width="medium">
                    <OrderDrill />
                  </Page>
                }
              />
              <Route
                path="/practice/:courseId/listen"
                element={
                  <Page width="medium">
                    <ListenDrill />
                  </Page>
                }
              />
              <Route
                path="/practice/:courseId/pronounce"
                element={
                  <Page width="medium">
                    <PronunciationDrill />
                  </Page>
                }
              />
              {/* Old standalone route, kept so existing links don't 404. */}
              <Route path="/pronunciation" element={<Navigate to="/practice" replace />} />
              <Route
                path="/courses/:courseId/complete"
                element={
                  <Page width="medium">
                    <CompletionScreen />
                  </Page>
                }
              />
              <Route
                path="/courses/:courseId/timeline"
                element={
                  <Page width="wide">
                    <CourseTimeline />
                  </Page>
                }
              />
              {import.meta.env.DEV && (
                <Route
                  path="/kitchen-sink"
                  element={
                    <Page width="wide">
                      <KitchenSink />
                    </Page>
                  }
                />
              )}
              <Route
                path="*"
                element={
                  <Page width="medium">
                    <NotFound />
                  </Page>
                }
              />
              </Route>
            </Routes>
          </PageTransition>
        </ErrorBoundary>
      </main>

      {!focusMode && <Footer />}
    </div>
  )
}

export default App
