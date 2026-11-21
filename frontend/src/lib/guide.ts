/** Set once a visitor has seen the role guide; first-time sign-ups are sent to /guide. */
export const GUIDE_SEEN_KEY = "hd-guide-seen";

export function guideSeen(): boolean {
  try {
    return localStorage.getItem(GUIDE_SEEN_KEY) === "1";
  } catch {
    return true; // storage blocked: never trap anyone on the guide
  }
}

export function markGuideSeen(): void {
  try {
    localStorage.setItem(GUIDE_SEEN_KEY, "1");
  } catch {
    /* private mode: the guide may show again, which is fine */
  }
}
