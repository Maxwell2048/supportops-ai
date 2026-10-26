import type { Priority, TicketStatus } from "../api/contracts.ts";

const labels: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  waiting_customer: "Waiting for customer",
  resolved: "Resolved",
  closed: "Closed",
};
const dateTime = new Intl.DateTimeFormat("en-AU", {
  timeZone: "Australia/Perth",
  dateStyle: "medium",
  timeStyle: "short",
});
export function Status({ status }: { status: TicketStatus }) {
  return (
    <span className={`status status-${status}`}>
      <span aria-hidden="true" />
      {labels[status]}
    </span>
  );
}
export function PriorityLabel({ priority }: { priority: Priority }) {
  return (
    <span className={`priority priority-${priority}`}>
      <span aria-hidden="true">
        {priority === "urgent" ? "↑↑" : priority === "high" ? "↑" : "•"}
      </span>{" "}
      {priority[0].toUpperCase() + priority.slice(1)}
    </span>
  );
}
export function Time({ value }: { value: string }) {
  return <time dateTime={value}>{dateTime.format(new Date(value))}</time>;
}
export function shortId(id: string) {
  return id.slice(0, 8).toUpperCase();
}
