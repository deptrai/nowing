'use client';

import { useState } from 'react';
import { Plus, ArrowUp, ArrowDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TemplateCard } from './TemplateCard';
import type { Template } from '@/lib/dashboard/template-api';
import { useLanguage } from '@/lib/i18n/LanguageContext';

interface TemplateGridProps {
  templates: Template[];
  currentUserId?: string | null;
  loading?: boolean;
  emptyCta?: () => void;
  onEdit?: (template: Template) => void;
  onDelete?: (template: Template) => void;
  onReorder?: (sourceId: string, targetId: string) => void;
  canReorder?: boolean;
}

export function TemplateGrid({
  templates,
  currentUserId,
  loading,
  emptyCta,
  onEdit,
  onDelete,
  onReorder,
  canReorder = false,
}: TemplateGridProps) {
  const { app } = useLanguage();
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  if (loading) {
    return (
      <div
        data-testid="template-grid-skeleton"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className={cn(
              'rounded-xl border border-light-200 dark:border-dark-200',
              'bg-light-primary dark:bg-dark-primary p-4 h-48 animate-pulse',
            )}
          />
        ))}
      </div>
    );
  }

  if (templates.length === 0) {
    return (
      <div
        data-testid="template-grid-empty"
        className="flex flex-col items-center justify-center rounded-xl border border-light-200 dark:border-dark-200 bg-light-primary dark:bg-dark-primary p-12 text-center"
      >
        <p className="text-sm font-medium text-black dark:text-white">
          {app.templates.emptyTitle}
        </p>
        <p className="mt-1 text-xs text-black/60 dark:text-white/60">
          {app.templates.emptyDesc}
        </p>
        {emptyCta && (
          <button
            type="button"
            data-testid="template-empty-cta"
            onClick={emptyCta}
            className={cn(
              'mt-4 inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-medium',
              'bg-accent text-white hover:bg-accent-hover',
            )}
          >
            <Plus size={14} />
            {app.templates.createTemplateBtn}
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      data-testid="template-grid"
      className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
    >
      {templates.map((template, index) => {
        const isDraggingThis = draggedId === template.id;
        const isDragTarget = dragOverId === template.id;

        return (
          <div
            key={template.id}
            data-testid={`template-grid-item-${template.id}`}
            draggable={canReorder && !!onReorder}
            onDragStart={(e) => {
              if (!canReorder || !onReorder) return;
              setDraggedId(template.id);
              e.dataTransfer.setData('text/plain', template.id);
              e.dataTransfer.effectAllowed = 'move';
            }}
            onDragEnd={() => {
              setDraggedId(null);
              setDragOverId(null);
            }}
            onDragOver={(e) => {
              if (!canReorder || !onReorder) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = 'move';
              if (dragOverId !== template.id) {
                setDragOverId(template.id);
              }
            }}
            onDragLeave={() => {
              if (dragOverId === template.id) {
                setDragOverId(null);
              }
            }}
            onDrop={(e) => {
              if (!canReorder || !onReorder) return;
              e.preventDefault();
              const sourceId = e.dataTransfer.getData('text/plain') || draggedId;
              setDraggedId(null);
              setDragOverId(null);
              if (sourceId && sourceId !== template.id) {
                onReorder(sourceId, template.id);
              }
            }}
            className={cn(
              'relative rounded-xl transition-all duration-150',
              canReorder && onReorder && 'cursor-move',
              isDraggingThis && 'opacity-40 scale-[0.98]',
              isDragTarget && 'ring-2 ring-accent ring-offset-2 ring-offset-light-primary dark:ring-offset-dark-primary',
            )}
          >
            {canReorder && onReorder && (
              <div className="absolute top-2 right-2 z-10 flex items-center gap-1 bg-light-primary/90 dark:bg-dark-primary/90 rounded px-1 py-0.5 border border-light-200 dark:border-dark-200">
                <button
                  type="button"
                  data-testid={`template-reorder-up-${template.id}`}
                  disabled={index === 0}
                  onClick={() => {
                    const prevTemplate = templates[index - 1];
                    if (prevTemplate) onReorder(template.id, prevTemplate.id);
                  }}
                  className="p-0.5 text-black/50 dark:text-white/50 hover:text-accent disabled:opacity-30"
                  aria-label="Move template up"
                >
                  <ArrowUp size={12} />
                </button>
                <button
                  type="button"
                  data-testid={`template-reorder-down-${template.id}`}
                  disabled={index === templates.length - 1}
                  onClick={() => {
                    const nextTemplate = templates[index + 1];
                    if (nextTemplate) onReorder(template.id, nextTemplate.id);
                  }}
                  className="p-0.5 text-black/50 dark:text-white/50 hover:text-accent disabled:opacity-30"
                  aria-label="Move template down"
                >
                  <ArrowDown size={12} />
                </button>
              </div>
            )}
            <TemplateCard
              template={template}
              currentUserId={currentUserId}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          </div>
        );
      })}
    </div>
  );
}
