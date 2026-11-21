"""What the help assistant knows: a short product overview, one section per role and one
note per page. Only the overview, the asker's role and the page they are on are sent with a
question, so each call stays small."""

from typing import Literal

Role = Literal["admin", "manager", "creator"]

OVERVIEW = """Heimdall is an AI brand-governance checkpoint between "draft" and "publish". \
Tagline: Nothing crosses unchecked.
Roles: an ADMIN owns a brand (guidelines, facts, team); a CREATOR writes content and fixes \
flags; a MANAGER approves or sends content back. Everyone picks a role at sign-up (email and \
password, or Continue with Google) and lands in their own portal at sign-in.
How a check works: the creator uploads text, a PDF, an image or a short video (60 s max). \
Personal data (emails, phone numbers, card numbers, ID numbers, the brand's confidential \
terms) is masked before any AI sees it. Four layers then check it: (1) rules in code (banned \
words, required phrases), (2) brand guidelines (matching rules + an AI judge), (3) claims \
against approved facts, (4) visuals with a vision model. Every flag cites its source: a rule \
code (R-012), a fact code (F-003) or the built-in claim policy SYS-CLAIM-001. Code drops any \
AI flag whose source was not given to the AI or whose quote is not in the content ("no \
source, no flag"). AI advises, people decide: nothing is published or blocked automatically.
Content statuses: Checking -> Needs your review (creator) -> With manager -> Approved; a \
manager can Request changes (Sent back) or Re-evaluate (fresh AI check, back to the creator).
Flag statuses: open, accepted (fix applied), edited (creator's own wording), dismissed \
(reason required), excepted (manager approved an exception, reason required).
The header shows the AI disclosure page (which AI services were used and what they receive) \
and a Sign out button. A creator or manager on several brands' teams has a "Following" menu \
in the header to switch brand."""

ROLES: dict[str, str] = {
    "admin": """ADMIN portal tabs: Guidelines, Facts, Website check, Assets, Team, Settings, \
Insights, AI disclosure.
Getting started: 1) Guidelines: upload the brand guideline, 2) approve the extracted rules, \
3) Facts: add or import approved facts, 4) Team: add creators and managers, 5) Settings: \
confidential terms and claim policy.
Building the team: open Team. The left list shows who is on the brand's team (admin, \
managers, creators) with a remove button. On the right is the "Add people" panel (a \
section, not a button): switch between Creators and Managers, search by name or \
email, press Add. People must first sign up themselves as a creator or manager; then \
they appear in the search. A creator can be on several admins' teams and chooses which \
brand to follow. Admins cannot be removed.""",
    "creator": """CREATOR portal tabs: My content, New check, AI disclosure.
If you see "You are not on a team yet": ask a brand admin to add your email from their Team \
tab, then press Check again.
Workflow: New check -> paste text or upload a file (PDF, image with alt text, or a video \
<= 60 s with optional captions) and give it a title -> Heimdall checks it (usually under a \
minute) -> open it from My content -> work through the flags -> Submit to manager.
On each flag: Accept fix (applies the suggested fix in a new version), Edit wording (write \
your own fix), Dismiss (give a reason). "Choose all fixes" / "Apply chosen fixes" applies \
several at once. Fixed versions are not re-checked by AI; to have AI check again, use \
"Upload revised script". Highlighted text in the content pane is the evidence; click a \
highlight to jump to its flag.
Submit to manager: type the manager's email. It is checked as you type: a green "Found" \
means a manager with that email is on this brand's team and Submit unlocks; a red message \
means no such manager. If the manager sends it back, read their comment, press Start \
revising, fix it and submit again. Version history lets you view older versions.""",
    "manager": """MANAGER portal tabs: Review queue, Insights, AI disclosure.
If you see "You are not on a team yet": ask a brand admin to add your email from their Team \
tab. Creators then submit to you by typing your email.
Review queue: content creators sent to you; filter by status (e.g. With manager, Sent back, \
Approved). Each row shows the creator's name and email.
Reviewing: the page shows "From <creator email>", the content with highlights and the open \
or dismissed flags (with the creator's dismissal reasons). Your decision box: Approve \
(comment optional), Request changes (comment required, at least 3 characters; it goes back \
to the same creator), Re-evaluate (runs a fresh AI check on the latest version and returns \
it to the same creator with new flags; your comment is attached). On a flag, Approve \
exception (with a reason) accepts it as an allowed exception for future checks. Comments at \
the bottom let you discuss with the creator.""",
}

# Longest matching path prefix wins.
PAGES: dict[str, str] = {
    "/admin/guidelines": """Guidelines page: "Upload guideline" takes one or more files \
(PDF, Word, PowerPoint, text, Markdown, CSV) or pasted text. Rules are extracted in the \
background ("Extracting rules" indicator) as one record per rule with a code (R-001), \
category, check type (deterministic = banned terms / required phrase run in code; semantic = \
checked by AI) and status. New rules are pending: approve or reject each one, or "Approve \
all pending". Only approved rules are used in checks. Edit a rule to fix its text, terms or \
category; "always on" sends it with every check. The verification report lists duplicate \
and contradicting rules, vague rules with a suggested rewrite, and missing categories.""",
    "/admin/facts": """Facts page: approved facts that claims are checked against (entity, \
attribute, value, unit, one-sentence statement, source, valid until). Add a fact, import a \
Facts CSV file, or search and filter by status. New facts are pending until approved. \
Expiry is checked in code: badges show expired facts and those expiring within 30 days. A \
claim that matches no approved fact is flagged under SYS-CLAIM-001.""",
    "/admin/website": """Website check: enter the brand's web page URLs; Heimdall compares \
them with the approved facts and lists proposed fact changes. Nothing changes until you \
Accept or Reject each one.""",
    "/admin/assets": """Asset library: approved logos, disclaimers and product copy. Add an \
asset with a description (and an optional image). Image checks read these descriptions, and \
missing disclaimers are fixed with the approved text.""",
    "/admin/team": """Team page: left = current members with role badges and a remove \
button; right = the "Add people" panel (not a button) with Creators / Managers tabs, \
a search box and Add buttons. Only people who signed up with that role appear.""",
    "/admin/settings": """Brand settings: Confidential terms (added terms are masked before \
any AI call), Claim policy (switch SYS-CLAIM-001 on or off), Readability target (minimum \
reading ease). Press Save settings.""",
    "/insights": """Insights: for a time range, flags raised, flags dismissed, items sent \
back and average time to approval; charts of flags per week and by category (each has a \
Table view); common dismissal reasons; guideline health (a rule dismissed in 40% or more of \
at least 5 flags is marked probably unclear, so the admin can rewrite it).""",
    "/disclosure": """AI disclosure: which AI providers and models were used, for what, how \
many calls (failed, from cache), what each receives and what is removed before any AI \
call.""",
    "/creator/new": """New check: give a Title, then Paste text or Upload a file (PDF, \
image with alt text, video up to 60 s with optional captions). If the brand has no approved \
rules yet, only claims are checked.""",
    "/creator/content": """Content review (creator): the left pane is the content with \
highlighted evidence; the right pane lists flags (tick Show resolved to see handled ones). \
Buttons: Accept fix, Edit wording, Dismiss, Choose all fixes, Apply chosen fixes, Submit to \
manager, Start revising (after Sent back), Upload revised script (new AI check), Try again \
(if a check failed), Version history, comments.""",
    "/creator": """My content: everything you have checked with its status and flag \
counts. Press New check to start; open a row to review its flags.""",
    "/manager/content": """Content review (manager): "From <email>" shows who sent it. The \
decision box has Approve, Request changes and Re-evaluate. Flags show open and dismissed \
ones with reasons; Approve exception is on each flag.""",
    "/manager": """Review queue: filter by status; each row shows the title, creator name \
and email, status and flag counts. Open a row to decide.""",
}


def page_note(path: str) -> str | None:
    """The note for the longest page prefix matching `path`."""
    matches = [p for p in PAGES if path == p or path.startswith(p + "/")]
    return PAGES[max(matches, key=len)] if matches else None


def context_for(role: str | None, path: str) -> str:
    """The guide text sent with a question: overview, the asker's role, the current page."""
    parts = [OVERVIEW]
    if role in ROLES:
        parts.append(ROLES[role])
    note = page_note(path)
    if note:
        parts.append(f"The user is on {path}. " + note)
    return "\n\n".join(parts)
