// Decorative, per-topic backdrop for the areas where sticky notes live
// (the live board and the closed-session summary): a scattered,
// low-opacity pattern of the dynamic's emoji icon (see
// agents/dynamic_generator.py — Groq already picks one per topic, e.g.
// ⛵ for a sailboat-themed retro). Deliberately not a generated image —
// that would need a paid image-generation API key; this reuses an icon
// the app already gets for free and renders it purely with CSS.
const POSITIONS = [
  { top: "-6%", left: "-4%", size: 96, rotate: -18, opacity: 0.1 },
  { top: "8%", left: "80%", size: 72, rotate: 12, opacity: 0.08 },
  { top: "55%", left: "2%", size: 64, rotate: 8, opacity: 0.09 },
  { top: "66%", left: "66%", size: 88, rotate: -10, opacity: 0.07 },
  { top: "28%", left: "40%", size: 130, rotate: 4, opacity: 0.06 },
] as const;

export function DynamicWatermark({ icon }: { icon: string }) {
  return (
    <div className="dynamic-watermark" aria-hidden="true">
      {POSITIONS.map((pos, i) => (
        <span
          key={i}
          style={{
            top: pos.top,
            left: pos.left,
            fontSize: pos.size,
            opacity: pos.opacity,
            transform: `rotate(${pos.rotate}deg)`,
          }}
        >
          {icon}
        </span>
      ))}
    </div>
  );
}
