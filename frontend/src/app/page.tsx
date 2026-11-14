import Link from "next/link";

import { PageHeader } from "@/components/shell/page-header";
import { ROLE_LINKS } from "@/lib/roles";

export default function Home() {
  return (
    <>
      <PageHeader
        title="Heimdall"
        description="The checkpoint between draft and publish. Choose a workspace."
      />
      <ul className="grid gap-4 sm:grid-cols-3">
        {ROLE_LINKS.map(({ href, label, description }) => (
          <li key={href}>
            <Link
              href={href}
              className="hover:bg-muted focus-visible:ring-ring block rounded-lg border p-5 transition-colors focus-visible:outline-none focus-visible:ring-2"
            >
              <span className="font-medium">{label}</span>
              <span className="text-muted-foreground mt-1 block text-sm">{description}</span>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
