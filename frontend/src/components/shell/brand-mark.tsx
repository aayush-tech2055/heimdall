/** The Heimdall mark: two arcs (the bridge being watched) and a gold eye. */
export function BrandMark({
  tone = "dark",
  size = 26,
}: {
  tone?: "dark" | "light";
  size?: number;
}) {
  const outer = tone === "light" ? "#ffffff" : "#0a0a0a";
  const inner = tone === "light" ? "#a5b4fc" : "#6366f1";
  return (
    <svg
      width={size}
      height={(size * 18) / 26}
      viewBox="0 0 58 40"
      aria-hidden
      className="shrink-0"
    >
      <path
        d="M5 34a24 24 0 0 1 48 0"
        fill="none"
        stroke={outer}
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d="M16 34a13 13 0 0 1 26 0"
        fill="none"
        stroke={inner}
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="29" cy="33" r="5.5" fill="#f5b544" />
    </svg>
  );
}
