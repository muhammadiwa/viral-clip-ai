
# 21 — Frontend Styleguide (Clean Code & OOP-ish React)

**Feature Slices**
```
/src/features/clips/{components,hooks,services,types,store.ts}
```

**Conventions**
- PascalCase components, camelCase vars, strict TS.
- Keep components small; extract hooks; avoid prop drilling.
- ErrorBoundary per route; toast for user errors.

**Sample Component (clean)**
```tsx
// ClipCard.tsx
import { Card } from "@/components/ui/card";
import { motion } from "framer-motion";
export function ClipCard({ clip, onOpen }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="p-4 space-y-3">
        <video src={clip.previewUrl} className="w-full rounded-lg" controls />
        <div className="flex items-center justify-between">
          <div className="font-semibold">{clip.title}</div>
          <div className="text-sm opacity-70">{Math.round(clip.score)}%</div>
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={() => onOpen?.(clip.id)}>Open</button>
        </div>
      </Card>
    </motion.div>
  );
}
```
