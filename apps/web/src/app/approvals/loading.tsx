import { ListSkeleton } from "@/components/ui/Skeleton";

export default function ApprovalsLoading() {
  return (
    <div aria-busy="true">
      <ListSkeleton rows={3} />
    </div>
  );
}
