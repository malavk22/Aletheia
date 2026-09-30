import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter'
import '@fontsource-variable/source-serif-4'
// Display typeface for the large wordmark (see --font-display in index.css).
// opsz.css includes its "optical size" axis, which AnimatedWordmark uses to get
// the sharp large-size cut.
import '@fontsource-variable/newsreader/opsz.css'
import './index.css'
import { DesignPreview } from './pages/DesignPreview.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DesignPreview />
  </StrictMode>,
)
