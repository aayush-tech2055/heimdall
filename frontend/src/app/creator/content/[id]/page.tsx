"use client";

import { useParams } from "next/navigation";

import { RoleGate } from "@/components/auth/role-gate";
import { ReviewWorkspace } from "@/components/content/review-workspace";

export default function CreatorReviewPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RoleGate roles={["creator"]}>
      {() => (
        <ReviewWorkspace contentId={id} mode="creator" backHref="/creator" />
      )}
    </RoleGate>
  );
}
