import { create } from 'zustand';
import type { Notification } from '@/types';
import { notificationApi } from '@/lib/api';

interface NotificationState {
  items: Notification[];
  unreadCount: number;
  loading: boolean;

  fetch: () => Promise<void>;
  fetchUnreadCount: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  pushFromWebSocket: (notif: Notification) => void;
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  items: [],
  unreadCount: 0,
  loading: false,

  async fetch() {
    set({ loading: true });
    try {
      const [items, { unread }] = await Promise.all([
        notificationApi.list({ limit: 50 }),
        notificationApi.unreadCount(),
      ]);
      set({ items, unreadCount: unread });
    } finally {
      set({ loading: false });
    }
  },

  async fetchUnreadCount() {
    try {
      const { unread } = await notificationApi.unreadCount();
      set({ unreadCount: unread });
    } catch {
      // ignore
    }
  },

  async markRead(id) {
    await notificationApi.markRead(id);
    set((s) => ({
      items: s.items.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      unreadCount: Math.max(0, s.unreadCount - 1),
    }));
  },

  async markAllRead() {
    await notificationApi.markAllRead();
    set((s) => ({
      items: s.items.map((n) => ({ ...n, is_read: true })),
      unreadCount: 0,
    }));
  },

  pushFromWebSocket(notif) {
    const exists = get().items.some((n) => n.id === notif.id);
    if (exists) return;
    set((s) => ({
      items: [notif, ...s.items].slice(0, 100),
      unreadCount: s.unreadCount + 1,
    }));
  },
}));
