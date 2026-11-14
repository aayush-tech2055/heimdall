"use client";

import { useParams } from "next/navigation";

import { RoleGate } from "@/components/auth/role-gate";
import { ReviewWorkspace } from "@/components/content/review-workspace";

export default function ManagerReviewPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RoleGate roles={["manager", "admin"]}>
      {() => (
        <ReviewWorkspace contentId={id} mode="manager" backHref="/manager" />
      )}
    </RoleGate>
  );
}
