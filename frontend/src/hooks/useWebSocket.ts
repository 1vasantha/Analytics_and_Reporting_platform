'use client';

import { useEffect, useRef } from 'react';
import { tokenStorage } from '@/lib/api';
import { useNotificationStore } from '@/stores/notifications';
import { useQueryClient } from '@tanstack/react-query';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

type WsMessage =
  | { type: 'connected'; org: string }
  | { type: 'ping' }
  | { type: 'events_ingested'; count: number }
  | {
      type: 'alert_triggered';
      notification_id: string;
      alert_id: string;
      title: string;
      message: string;
      observed: number;
      threshold: number;
    };

/**
 * Maintains a persistent WebSocket connection while the user is authenticated.
 * Dispatches incoming messages to relevant stores / TanStack Query caches.
 */
export function useWebSocket(enabled: boolean) {
  const ref = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const queryClient = useQueryClient();
  const pushNotification = useNotificationStore((s) => s.pushFromWebSocket);
  const refreshUnread = useNotificationStore((s) => s.fetchUnreadCount);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    const connect = () => {
      const token = tokenStorage.getAccess();
      if (!token) return;

      const ws = new WebSocket(`${WS_URL}/ws?token=${encodeURIComponent(token)}`);
      ref.current = ws;

      ws.onmessage = (ev) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }

        if (msg.type === 'events_ingested') {
          // Invalidate widget data queries so dashboards refresh
          queryClient.invalidateQueries({ queryKey: ['widget-data'] });
          queryClient.invalidateQueries({ queryKey: ['metric-query'] });
        } else if (msg.type === 'alert_triggered') {
          pushNotification({
            id: msg.notification_id,
            alert_id: msg.alert_id,
            title: msg.title,
            message: msg.message,
            severity: 'warning',
            is_read: false,
            metadata: { observed: msg.observed, threshold: msg.threshold },
            created_at: new Date().toISOString(),
          });
          refreshUnread();
        }
      };

      ws.onclose = () => {
        if (!cancelled) {
          reconnectTimer.current = window.setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      ref.current?.close();
    };
  }, [enabled, queryClient, pushNotification, refreshUnread]);
}
