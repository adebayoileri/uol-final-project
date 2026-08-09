import Container from './Container'

export default function Footer() {
  return (
    <footer className="border-hairline mt-24 border-t py-8">
      <Container width="wide">
        <p className="text-caption text-fg-faint">
          SuperLearned · final-year project · courses generated locally, retained with FSRS spaced
          repetition
        </p>
      </Container>
    </footer>
  )
}
