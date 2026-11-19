/** Re-mounted on every navigation, so each page arrives with a short rise-and-fade. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="hd-page">{children}</div>;
}
