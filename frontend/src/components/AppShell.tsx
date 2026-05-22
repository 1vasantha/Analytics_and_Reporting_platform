'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  Bell,
  FileText,
  Settings,
  LogOut,
  Activity,
  AlertTriangle,
  ChevronDown,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useNotificationStore } from '@/stores/notifications';
import { cn, formatRelative } from '@/lib/utils';

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, organization, logout, isAuthenticated } = useAuthStore();
  const { unreadCount, fetchUnreadCount, items, fetch: fetchNotifs, markRead, markAllRead } =
    useNotificationStore();
  const [notifOpen, setNotifOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace('/login');
    } else {
      fetchUnreadCount();
      const interval = setInterval(fetchUnreadCount, 30_000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, router, fetchUnreadCount]);

  if (!isAuthenticated) {
    return null;
  }

  const navItems = [
    { href: '/dashboards', label: 'Dashboards', icon: LayoutDashboard },
    { href: '/alerts', label: 'Alerts', icon: AlertTriangle },
    { href: '/reports', label: 'Reports', icon: FileText },
    { href: '/settings', label: 'Settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-60 border-r border-ink-200 bg-white flex flex-col">
        <div className="p-6 border-b border-ink-200">
          <Link href="/dashboards" className="flex items-center gap-2 group">
            <div className="w-7 h-7 rounded bg-ink-900 flex items-center justify-center">
              <Activity className="w-4 h-4 text-accent" />
            </div>
            <div className="font-display text-lg font-medium tracking-tight">
              Analytics
            </div>
          </Link>
          {organization && (
            <div className="mt-3 text-xs text-ink-500 uppercase tracking-wider">
              {organization.name}
            </div>
          )}
        </div>

        <nav className="flex-1 p-3 space-y-0.5">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active =
              pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded text-sm transition-all',
                  active
                    ? 'bg-ink-900 text-white'
                    : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
                )}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        {user && (
          <div className="p-3 border-t border-ink-200">
            <div className="relative">
              <button
                onClick={() => setMenuOpen((v) => !v)}
                className="w-full flex items-center gap-3 p-2 rounded hover:bg-ink-100 transition-all"
              >
                <div className="w-8 h-8 rounded-full bg-ink-900 text-white flex items-center justify-center text-xs font-medium">
                  {user.full_name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 text-left min-w-0">
                  <div className="text-sm font-medium text-ink-900 truncate">
                    {user.full_name}
                  </div>
                  <div className="text-xs text-ink-500 capitalize">{user.role}</div>
                </div>
                <ChevronDown className="w-4 h-4 text-ink-400" />
              </button>

              {menuOpen && (
                <div className="absolute bottom-full mb-2 left-0 right-0 card p-1 z-10">
                  <button
                    onClick={async () => {
                      await logout();
                      router.push('/login');
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-700 hover:bg-ink-100 rounded transition-all"
                  >
                    <LogOut className="w-4 h-4" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-ink-200 bg-white flex items-center justify-end px-6">
          <div className="relative">
            <button
              onClick={() => {
                setNotifOpen((v) => !v);
                if (!notifOpen) fetchNotifs();
              }}
              className="relative p-2 rounded hover:bg-ink-100 transition-all"
            >
              <Bell className="w-4 h-4 text-ink-700" />
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-accent" />
              )}
            </button>

            {notifOpen && (
              <div className="absolute right-0 top-full mt-2 w-96 card z-20 max-h-[600px] flex flex-col">
                <div className="p-3 border-b border-ink-200 flex items-center justify-between">
                  <div className="font-medium text-sm">
                    Notifications
                    {unreadCount > 0 && (
                      <span className="ml-2 text-xs text-accent">({unreadCount} new)</span>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <button
                      onClick={() => markAllRead()}
                      className="text-xs text-ink-500 hover:text-ink-900"
                    >
                      Mark all read
                    </button>
                  )}
                </div>
                <div className="overflow-y-auto flex-1">
                  {items.length === 0 ? (
                    <div className="p-8 text-center text-sm text-ink-400">
                      No notifications yet
                    </div>
                  ) : (
                    items.map((notif) => (
                      <button
                        key={notif.id}
                        onClick={() => !notif.is_read && markRead(notif.id)}
                        className={cn(
                          'w-full p-3 text-left border-b border-ink-100 hover:bg-ink-50 transition-all',
                          !notif.is_read && 'bg-accent-50/30',
                        )}
                      >
                        <div className="flex items-start gap-2">
                          {!notif.is_read && (
                            <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-ink-900">
                              {notif.title}
                            </div>
                            <div className="text-xs text-ink-600 mt-0.5">
                              {notif.message}
                            </div>
                            <div className="text-[11px] text-ink-400 mt-1">
                              {formatRelative(notif.created_at)}
                            </div>
                          </div>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
