# Accessibility audit of Heimdall's interface (task 14.3)

**Method (2026-11-15).** Every screen was opened in Chrome (headless, driven by Playwright) after
signing in as the seeded admin, creator and manager, and checked with **axe-core 4.10** against the
WCAG 2.0 and 2.1 A and AA rules. Content pages were audited with real review results: a text item
with 35 flags, a PDF with page boxes and a video with a flag timeline. Screenshots from the same run
are in [`screenshots/`](screenshots/).

| Screen | First run | After fixes |
|---|---|---|
| Sign in | 0 | 0 |
| Admin: guidelines, facts | 3 (critical: tab filters pointed at missing panels; serious: low contrast on rejected rules) | 0 |
| Admin: website check, assets, settings | 0 | 0 |
| Insights | 1 (critical: tab filter) | 0 |
| AI disclosure | 0 | 0 |
| Creator: my content, new check, review (text, PDF, video) | 0 | 0 |
| Manager: queue | 1 (critical: tab filter) | 0 |
| Manager: review | 0 | 0 |
| **Total (15 screens)** | **5 violation types** | **0** |

## Fixes

- **Filters are toggle buttons, not ARIA tabs.** Status and time-range filters used tab widgets
  without tab panels, so `aria-controls` pointed at nothing. They are now a labelled group of buttons
  with `aria-pressed` (`components/ui/filter-tabs.tsx`).
- **No faded text.** Rejected rules, resolved flags and dismissed highlights were dimmed with
  opacity, which dropped text below 4.5:1. They now use a tinted background, a dotted underline and
  their status badge; grey badges use a darker text colour (more than 4.5:1).

## Built in from the start

- A "Skip to content" link, a single `main` landmark, one `h1` per page and headed sections.
- Keyboard: every action is a button or link; text highlights, PDF boxes and video timeline marks are
  focusable and open their flag with Enter or Space. On sign-in the Tab order is skip link → home →
  email → password → Sign in, each with a visible focus ring.
- Every input has a label; icons are `aria-hidden` and icon-only buttons have an `aria-label`.
- Identity never by colour alone: severity is written on every flag ("High", "Medium", "Low"),
  statuses are words, and charts come with a table view.
- Loading and result messages use `role="status"`, errors `role="alert"`.

## Limits

- Checked with an automated tool plus a keyboard walk-through of sign-in; a full screen-reader pass
  (VoiceOver or NVDA) is part of user testing (task 10.4).
- Dark mode is not offered; the interface is light only.
