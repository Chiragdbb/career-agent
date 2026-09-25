"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useEventStream } from "@/lib/useEventStream";
import { cn } from "@/lib/cn";

type Notification = {
  id: string;
  title: string;
  body: string | null;
  status: string;
  created_at: string;
  data?: Record<string, unknown> | null;
  notification_type?: string | null;
};

function hrefFromNotification(item: Notification): string {
  const data = item.data || {};
  if (typeof data.href === "string" && data.href.startsWith("/")) {
    return data.href;
  }
  if (typeof data.application_id === "string" && data.application_id) {
    return `/approvals?application=${data.application_id}`;
  }
  if (typeof data.outreach_id === "string" && data.outreach_id) {
    return `/outreach/${data.outreach_id}`;
  }
  if (item.notification_type === "human_task") return "/approvals";
  return "/settings?tab=notifications";
}

export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await apiFetch("/api/v1/notifications?status=unread");
      if (response.ok) {
        setItems((await response.json()) as Notification[]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEventStream({
    onEvent: (event) => {
      if (event.type === "notification_created") void refresh();
    },
  });

  async function markAllRead() {
    await apiFetch("/api/v1/notifications/read-all", { method: "POST" });
    await refresh();
  }

  async function openItem(item: Notification) {
    const href = hrefFromNotification(item);
    setOpen(false);
    await apiFetch(`/api/v1/notifications/${item.id}/read`, {
      method: "POST",
    }).catch(() => null);
    router.push(href);
  }

  const unreadCount = items.length;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-full border border-line p-2 text-ink hover:bg-paper"
        aria-label="Notifications"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-brick px-1 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 top-[calc(100%+8px)] z-50 w-80 rounded-[10px] border border-line bg-paper-raised shadow-[0_8px_24px_rgba(22,35,31,0.12)]">
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <p className="text-sm font-semibold text-ink">Notifications</p>
            <button
              type="button"
              onClick={() => void markAllRead()}
              className="text-xs text-gold hover:underline"
            >
              Mark all read
            </button>
          </div>
          <ul className="max-h-72 overflow-y-auto">
            {loading ? (
              <li className="px-3 py-4 text-sm text-text-muted">Loading…</li>
            ) : items.length === 0 ? (
              <li className="px-3 py-4 text-sm text-text-muted">
                No unread notifications
              </li>
            ) : (
              items.map((item) => (
                <li key={item.id} className="border-b border-line/60">
                  <button
                    type="button"
                    className={cn(
                      "w-full px-3 py-2.5 text-left text-sm hover:bg-paper",
                      item.status === "unread" && "bg-gold/5",
                    )}
                    onClick={() => void openItem(item)}
                  >
                    <p className="font-medium text-ink">{item.title}</p>
                    {item.body ? (
                      <p className="mt-0.5 text-text-muted">{item.body}</p>
                    ) : null}
                    <p className="mt-1 text-[11px] font-semibold text-coral">
                      Open →
                    </p>
                  </button>
                </li>
              ))
            )}
          </ul>
          <div className="border-t border-line px-3 py-2">
            <Link
              href="/settings?tab=notifications"
              className="text-xs text-gold hover:underline"
            >
              View all →
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
