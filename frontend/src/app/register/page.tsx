'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/stores/auth';

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const isLoading = useAuthStore((s) => s.isLoading);

  const [form, setForm] = useState({
    email: '',
    password: '',
    full_name: '',
    organization_name: '',
  });
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await register(form);
      router.push('/dashboards');
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Registration failed');
    }
  }

  function update<K extends keyof typeof form>(key: K, val: string) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  return (
    <div className="min-h-screen grid-bg flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <div className="mb-10 text-center">
          <div className="font-display text-4xl font-medium tracking-tight mb-2">
            Analytics
          </div>
          <div className="text-sm text-ink-500">Create your workspace</div>
        </div>

        <form onSubmit={onSubmit} className="card p-8 space-y-5">
          {error && (
            <div className="px-3 py-2 rounded bg-accent-50 text-accent-700 text-sm border border-accent-100">
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
              Organization
            </label>
            <input
              required
              value={form.organization_name}
              onChange={(e) => update('organization_name', e.target.value)}
              placeholder="Acme Inc."
              className="input-base"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
              Your name
            </label>
            <input
              required
              value={form.full_name}
              onChange={(e) => update('full_name', e.target.value)}
              placeholder="Jane Doe"
              className="input-base"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
              Work email
            </label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => update('email', e.target.value)}
              placeholder="jane@acme.com"
              className="input-base"
              autoComplete="email"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-600 uppercase tracking-wide">
              Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => update('password', e.target.value)}
              className="input-base"
              autoComplete="new-password"
            />
            <div className="text-xs text-ink-400 mt-1">
              At least 8 characters with a letter and a digit
            </div>
          </div>

          <button type="submit" disabled={isLoading} className="btn-primary w-full">
            {isLoading ? 'Creating workspace…' : 'Create workspace'}
          </button>

          <div className="text-center text-sm text-ink-500">
            Already have an account?{' '}
            <Link href="/login" className="text-ink-900 underline underline-offset-4 hover:text-accent">
              Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
