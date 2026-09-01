export function isDraftedOutreachStatus(status: string): boolean {
  const s = status.toLowerCase();
  return s === "draft" || s === "pending_approval" || s.includes("draft");
}

export function isApprovedOutreachStatus(status: string): boolean {
  return status.toLowerCase() === "approved";
}

export function outreachColumnForStatus(status: string): string {
  const s = status.toLowerCase();
  if (s.includes("sent")) return "sent";
  if (s.includes("approved")) return "approved";
  if (s.includes("draft") || s === "pending_approval") return "drafted";
  return "to_contact";
}
