'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/hooks/useAuth';
import { TemplateFilters, type TemplateTab } from '@/components/Dashboard/TemplateFilters';
import { TemplateGrid } from '@/components/Dashboard/TemplateGrid';
import { TemplateEditor } from '@/components/Dashboard/TemplateEditor';
import {
  listTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
} from '@/lib/dashboard/template-api';
import type { Template, TemplateFormState } from '@/lib/dashboard/template-api';
import { useLanguage } from '@/lib/i18n/LanguageContext';

export default function DashboardTemplatesPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { app } = useLanguage();

  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<TemplateTab>('all');
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listTemplates();
      setTemplates(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load templates';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const filteredTemplates = useMemo(() => {
    const q = search.trim().toLowerCase();
    return templates.filter((t) => {
      if (q) {
        const hay = `${t.name} ${t.description ?? ''} ${t.tags.join(' ')}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      switch (activeTab) {
        case 'built-in':
          return t.isBuiltIn;
        case 'my':
          return !t.isBuiltIn && t.scope === 'personal' && t.userId === user?.id;
        case 'workspace':
          return false;
        case 'all':
        default:
          return true;
      }
    });
  }, [templates, search, activeTab, user]);

  const handleCreate = useCallback(() => {
    if (!user) {
      toast.info('Please sign in to create custom templates');
      router.push('/login?next=/dashboard/templates');
      return;
    }
    setEditingTemplate(null);
    setEditorOpen(true);
  }, [user, router]);

  const handleEdit = useCallback((template: Template) => {
    if (template.isBuiltIn) {
      toast.error('Built-in templates cannot be edited');
      return;
    }
    if (template.userId !== user?.id) {
      toast.error('You can only edit your own templates');
      return;
    }
    setEditingTemplate(template);
    setEditorOpen(true);
  }, [user?.id]);

  const handleDelete = useCallback(async (template: Template) => {
    if (template.isBuiltIn) {
      toast.error('Built-in templates cannot be deleted');
      return;
    }
    if (template.userId !== user?.id) {
      toast.error('You can only delete your own templates');
      return;
    }
    if (!confirm(`Delete template "${template.name}"?`)) return;
    try {
      await deleteTemplate(template.id);
      setTemplates((prev) => prev.filter((t) => t.id !== template.id));
      toast.success('Template deleted');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      toast.error(message);
    }
  }, [user?.id]);

  const handleSave = useCallback(async (form: TemplateFormState, id?: string) => {
    try {
      const saved = id ? await updateTemplate(id, form) : await createTemplate(form);
      setTemplates((prev) => {
        const next = [...prev];
        const idx = next.findIndex((t) => t.id === saved.id);
        if (idx >= 0) {
          next[idx] = saved;
        } else {
          next.unshift(saved);
        }
        return next;
      });
      toast.success(id ? 'Template updated' : 'Template created');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Save failed';
      toast.error(message);
      throw err;
    }
  }, []);

  const handleReorder = useCallback(
    async (sourceId: string, targetId: string) => {
      const myTemplates = templates.filter(
        (t) => !t.isBuiltIn && t.scope === 'personal' && t.userId === user?.id,
      );
      const sourceIdx = myTemplates.findIndex((t) => t.id === sourceId);
      const targetIdx = myTemplates.findIndex((t) => t.id === targetId);
      if (sourceIdx < 0 || targetIdx < 0 || sourceIdx === targetIdx) return;

      const updated = [...templates];
      const realSourceIdx = updated.findIndex((t) => t.id === sourceId);
      const realTargetIdx = updated.findIndex((t) => t.id === targetId);
      const [moved] = updated.splice(realSourceIdx, 1);
      updated.splice(realTargetIdx, 0, moved);
      setTemplates(updated);

      try {
        const payload = updated
          .filter((t) => !t.isBuiltIn && t.userId === user?.id)
          .map((t, idx) => ({ id: t.id, displayOrder: idx }));
        await fetch('/api/templates/reorder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items: payload }),
        });
      } catch {
        toast.error('Failed to save template order');
      }
    },
    [templates, user?.id],
  );

  return (
    <div
      data-testid="dashboard-templates-page"
      className="space-y-6 max-w-6xl mx-auto"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-black dark:text-white">
            {app.templates.title}
          </h1>
          <p className="text-xs text-black/60 dark:text-white/60 mt-1">
            {app.templates.subtitle}
          </p>
        </div>
        <button
          type="button"
          data-testid="template-create-btn"
          onClick={handleCreate}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-all shrink-0 self-start sm:self-auto"
        >
          <Plus size={15} />
          {app.templates.createTemplateBtn}
        </button>
      </div>

      <TemplateFilters
        search={search}
        onSearch={setSearch}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {loading ? (
        <div className="py-16 flex flex-col items-center justify-center text-black/40 dark:text-white/40 gap-2">
          <Loader2 size={24} className="animate-spin text-blue-600" />
          <span className="text-xs">{app.common.loading}</span>
        </div>
      ) : (
        <TemplateGrid
          templates={filteredTemplates}
          currentUserId={user?.id}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onReorder={handleReorder}
        />
      )}

      <TemplateEditor
        isOpen={editorOpen}
        template={editingTemplate}
        onSubmit={handleSave}
        onClose={() => setEditorOpen(false)}
      />
    </div>
  );
}
