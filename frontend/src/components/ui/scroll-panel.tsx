import { cn } from "cn";

/**
 * A region that scrolls inside itself (issue lists, rule lists, long content), so people
 * do not have to scroll the whole page. Soft shadows at the top and bottom show when there
 * is more to see. Focusable and labelled, so keyboard and screen-reader users can scroll it.
 */
export function ScrollPanel({
  label,
  className,
  surface = "var(--background)",
  style,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  /** Accessible name of the region, e.g. "Issues in this script". */
  label: string;
  /** Background behind the panel, so the edge shadows blend in. */
  surface?: string;
}) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      data-slot="scroll-panel"
      data-lenis-prevent
      className={cn(
        "hd-scroll focus-visible:ring-ring/50 rounded-lg outline-none focus-visible:ring-[3px]",
        className,
      )}
      {...props}
      style={{ ["--hd-scroll-bg" as string]: surface, ...style }}
    >
      {children}
    </div>
  );
}
