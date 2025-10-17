
# 20 — Frontend Spec

**Stack**
- React 18 + TypeScript + Vite
- TailwindCSS + shadcn/ui + Iconify
- Framer Motion, GSAP, React Three Fiber + drei, Lottie
- TanStack Query, Zustand, React Router, i18next, Zod, ESLint/Prettier/Vitest/RTL

**Key Screens**
Landing, Dashboard, Project Workspace, Movie Retell Studio, Asset Library, Team/Settings, Admin.

**State & Data Flow**
- TanStack Query (server state), Zustand (ephemeral UI state), WS/SSE for job progress.
- Uploads via tus-js-client or S3 multipart (resume/cancel).

**Performance & A11y**
- Initial JS < 200KB, code-splitting, lazy 3D; WAI-ARIA, keyboard shortcuts.
