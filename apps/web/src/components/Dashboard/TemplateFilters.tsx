'use client';

import { useEffect, useState } from 'react';
import { Search, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from '@/lib/i18n/LanguageContext';

export type TemplateTab = 'all' | 'built-in' | 'my' | 'workspace';

interface TemplateFiltersProps {
  search: string;
  onSearch: (value: string) => void;
  activeTab: TemplateTab;
  onTabChange: (tab: TemplateTab) => void;
}

export function TemplateFilters({
  search,
  onSearch,
  activeTab,
  onTabChange,
}: TemplateFiltersProps) {
  const { app } = useLanguage();
  const [localSearch, setLocalSearch] = useState(search);

  const tabs: { key: TemplateTab; label: string }[] = [
    { key: 'all', label: app.templates.tabAll },
    { key: 'built-in', label: app.templates.tabBuiltIn },
    { key: 'my', label: app.templates.tabMy },
    { key: 'workspace', label: app.templates.tabWorkspace },
  ];

  useEffect(() => {
    setLocalSearch(search);
  }, [search]);

  useEffect(() => {
    const timer = setTimeout(() => {
      onSearch(localSearch);
    }, 200);
    return () => clearTimeout(timer);
  }, [localSearch, onSearch]);

  return (
    <div
      data-testid="template-filters"
      className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
    >
      <div className="relative flex-1 max-w-md">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-black/40 dark:text-white/40"
        />
        <input
          data-testid="template-search-input"
          type="text"
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          placeholder={app.templates.searchPlaceholder}
          className={cn(
            'w-full rounded-lg border border-light-200 dark:border-dark-200',
            'bg-light-secondary dark:bg-dark-secondary pl-9 pr-3 py-1.5 text-sm',
            'text-black dark:text-white placeholder:text-black/40 dark:placeholder:text-white/40',
            'focus:outline-none focus:ring-1 focus:ring-sky-500',
          )}
        />
      </div>

      {/* Desktop tab pills */}
      <nav
        data-testid="template-tabs"
        className="hidden md:flex items-center gap-1 rounded-lg border border-light-200 dark:border-dark-200 bg-light-secondary dark:bg-dark-secondary p-1"
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              data-testid={`template-tab-${tab.key}`}
              onClick={() => onTabChange(tab.key)}
              className={cn(
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                isActive
                  ? 'bg-accent text-white'
                  : 'text-black/70 dark:text-white/70 hover:bg-light-200 dark:hover:bg-dark-200',
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* Mobile dropdown */}
      <div className="relative md:hidden">
        <select
          data-testid="template-tabs-mobile"
          value={activeTab}
          onChange={(e) => onTabChange(e.target.value as TemplateTab)}
          className={cn(
            'w-full appearance-none rounded-lg border border-light-200 dark:border-dark-200',
            'bg-light-secondary dark:bg-dark-secondary px-3 py-1.5 pr-9 text-sm',
            'text-black dark:text-white focus:outline-none focus:ring-1 focus:ring-sky-500',
          )}
        >
          {tabs.map((tab) => (
            <option key={tab.key} value={tab.key}>
              {tab.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={14}
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-black/50 dark:text-white/50"
        />
      </div>
    </div>
  );
}
