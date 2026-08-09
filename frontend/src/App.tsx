import { Route, Routes, useLocation } from 'react-router-dom'
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
import PronunciationDrill from './pages/PronunciationDrill'
import CompletionScreen from './pages/CompletionScreen'
import CourseTimeline from './pages/CourseTimeline'
import NotFound from './pages/NotFound'
import KitchenSink from './pages/KitchenSink'

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
  // Review is a focus surface: no footer competing with the card.
  const focusMode = location.pathname.endsWith('/review')

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
                    <ReviewSession />
                  </Page>
                }
              />
              <Route
                path="/pronunciation"
                element={
                  <Page width="medium">
                    <PronunciationDrill />
                  </Page>
                }
              />
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
            </Routes>
          </PageTransition>
        </ErrorBoundary>
      </main>

      {!focusMode && <Footer />}
    </div>
  )
}

export default App
