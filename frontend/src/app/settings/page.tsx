'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Key, Plus, Trash2, Upload, Copy, Check, FileText } from 'lucide-react';
import { ingestionApi } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { cn, formatRelative } from '@/lib/utils';

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const org = useAuthStore((s) => s.organization);

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-widest text-ink-500 mb-2">Workspace</div>
        <h1 className="font-display text-4xl font-medium tracking-tight">Settings</h1>
      </div>

      <div className="divider-rule mb-8" />

      {/* Profile */}
      <Section title="Profile">
        {user && (
          <div className="card p-5 space-y-3">
            <Row label="Name" value={user.full_name} />
            <Row label="Email" value={user.email} />
            <Row label="Role" value={user.role} valueClass="capitalize" />
            <Row label="Organization" value={org?.name || '—'} />
          </div>
        )}
      </Section>

      {/* API Keys */}
      <Section title="API Keys" description="Use these keys to ingest events programmatically. Keep them secret.">
        <ApiKeysSection />
      </Section>

      {/* CSV Upload */}
      <Section
        title="CSV Import"
        description="Upload a CSV with columns: event_name (required), source, user_id, session_id, value, occurred_at. Extra columns become properties."
      >
        <CsvUploadSection />
      </Section>
    </div>
  );
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-12">
      <div className="mb-4">
        <h2 className="font-display text-2xl font-medium">{title}</h2>
        {description && <p className="text-sm text-ink-500 mt-1">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function Row({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-ink-100 last:border-b-0">
      <div className="text-xs uppercase tracking-wide text-ink-500">{label}</div>
      <div className={cn('text-sm font-medium tabular', valueClass)}>{value}</div>
    </div>
  );
}

function ApiKeysSection() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: keys = [], isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: ingestionApi.listApiKeys,
  });

  const createKey = useMutation({
    mutationFn: () => ingestionApi.createApiKey(newKeyName),
    onSuccess: (data) => {
      setCreatedKey(data.key);
      setNewKeyName('');
      qc.invalidateQueries({ queryKey: ['api-keys'] });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => ingestionApi.revokeApiKey(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  });

  async function copyKey() {
    if (createdKey) {
      await navigator.clipboard.writeText(createdKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div>
      <div className="card overflow-hidden mb-3">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-ink-400">Loading…</div>
        ) : keys.length === 0 ? (
          <div className="p-8 text-center text-sm text-ink-500">
            No API keys yet. Create one to start ingesting events.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-ink-50 border-b border-ink-200">
              <tr>
                <th className="text-left px-4 py-2 text-xs uppercase tracking-wide text-ink-500 font-medium">
                  Name
                </th>
                <th className="text-left px-4 py-2 text-xs uppercase tracking-wide text-ink-500 font-medium">
                  Prefix
                </th>
                <th className="text-left px-4 py-2 text-xs uppercase tracking-wide text-ink-500 font-medium">
                  Last used
                </th>
                <th className="text-left px-4 py-2 text-xs uppercase tracking-wide text-ink-500 font-medium">
                  Status
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className="border-b border-ink-100 last:border-b-0">
                  <td className="px-4 py-3 font-medium">
                    <Key className="w-3.5 h-3.5 text-ink-400 inline mr-2" />
                    {k.name}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-600">
                    ak_{k.prefix}_••••
                  </td>
                  <td className="px-4 py-3 text-ink-500 text-xs">
                    {k.last_used_at ? formatRelative(k.last_used_at) : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    {k.revoked ? (
                      <span className="text-xs uppercase tracking-wider text-ink-400">Revoked</span>
                    ) : (
                      <span className="text-xs uppercase tracking-wider text-ink-700">Active</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!k.revoked && (
                      <button
                        onClick={() => {
                          if (confirm(`Revoke "${k.name}"? This cannot be undone.`)) {
                            revoke.mutate(k.id);
                          }
                        }}
                        className="text-xs text-accent-700 hover:text-accent-600"
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <button onClick={() => setShowNew(true)} className="btn-secondary">
        <Plus className="w-4 h-4" /> New API key
      </button>

      {showNew && !createdKey && (
        <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="card w-full max-w-md p-6">
            <div className="font-display text-xl font-medium mb-4">Create API key</div>
            <input
              autoFocus
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Production"
              className="input-base mb-4"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowNew(false)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => createKey.mutate()}
                disabled={createKey.isPending || !newKeyName}
                className="btn-primary"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {createdKey && (
        <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="card w-full max-w-lg p-6">
            <div className="font-display text-xl font-medium mb-2">Your new API key</div>
            <div className="text-sm text-accent-700 bg-accent-50 border border-accent-100 rounded px-3 py-2 mb-4">
              ⚠️ Copy this key now — it won't be shown again.
            </div>
            <div className="bg-ink-50 rounded p-3 font-mono text-xs break-all mb-4 border border-ink-200">
              {createdKey}
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={copyKey} className="btn-secondary">
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button
                onClick={() => {
                  setCreatedKey(null);
                  setShowNew(false);
                }}
                className="btn-primary"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CsvUploadSection() {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: jobs = [] } = useQuery({
    queryKey: ['ingestion-jobs'],
    queryFn: ingestionApi.listJobs,
    refetchInterval: 5000,
  });

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await ingestionApi.uploadCsv(file);
      qc.invalidateQueries({ queryKey: ['ingestion-jobs'] });
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  }

  return (
    <div>
      <label className="card p-8 flex flex-col items-center cursor-pointer hover:bg-ink-50 transition-all mb-4">
        <Upload className="w-8 h-8 text-ink-300 mb-2" />
        <div className="text-sm font-medium mb-1">
          {uploading ? 'Uploading…' : 'Click to upload a CSV'}
        </div>
        <div className="text-xs text-ink-400">Max 50MB</div>
        <input
          type="file"
          accept=".csv"
          onChange={handleFile}
          disabled={uploading}
          className="hidden"
        />
      </label>

      {error && (
        <div className="px-3 py-2 rounded bg-accent-50 text-accent-700 text-sm border border-accent-100 mb-4">
          {error}
        </div>
      )}

      {jobs.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-4 py-2 bg-ink-50 border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500 font-medium">
            Recent imports
          </div>
          <table className="w-full text-sm">
            <tbody>
              {jobs.slice(0, 10).map((job) => (
                <tr key={job.id} className="border-b border-ink-100 last:border-b-0">
                  <td className="px-4 py-3">
                    <FileText className="w-3.5 h-3.5 text-ink-400 inline mr-2" />
                    {job.filename}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <span
                      className={cn(
                        'uppercase tracking-wider px-1.5 py-0.5 rounded',
                        job.status === 'completed' && 'bg-ink-100 text-ink-700',
                        job.status === 'processing' && 'bg-accent-50 text-accent-700',
                        job.status === 'failed' && 'bg-accent-50 text-accent-700',
                        job.status === 'pending' && 'bg-ink-100 text-ink-500',
                      )}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-500 tabular">
                    {job.processed_rows} rows
                    {job.failed_rows > 0 && (
                      <span className="text-accent-700"> · {job.failed_rows} failed</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-400 text-right">
                    {formatRelative(job.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
