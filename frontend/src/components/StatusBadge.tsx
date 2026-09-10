type StatusType =
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "draft"
  | "published";

interface StatusBadgeProps {
  status: string;
}

const getStatusConfig = (status?: string) => {
  const s = (status || "active").toLowerCase();
  if (["completed", "published", "active", "connected"].includes(s))
    return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  if (["failed", "error", "disconnected"].includes(s))
    return "bg-red-500/10 text-red-400 border-red-500/20";
  if (["processing", "generating", "rendering"].includes(s))
    return "bg-blue-500/10 text-blue-400 border-blue-500/20";
  return "bg-amber-500/10 text-amber-400 border-amber-500/20"; // queued, draft, pending
};

const StatusBadge = ({ status }: StatusBadgeProps) => {
  const safeStatus = status || "active";
  const config = getStatusConfig(safeStatus);

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${config}`}
    >
      {safeStatus.charAt(0).toUpperCase() +
        safeStatus.slice(1).replace("_", " ")}
    </span>
  );
};

export default StatusBadge;
