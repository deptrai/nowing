'use client';

import DeleteChat from '@/components/DeleteChat';
import { formatTimeDifference } from '@/lib/utils';
import { History, ClockIcon, FileText, Globe2Icon, Search } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState, useMemo } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useChatsStore } from '@/lib/stores/chatsStore';
import type { Chat } from '@/lib/types';
import { useLanguage } from '@/lib/i18n/LanguageContext';

export const HistoryView = () => {
  const { app } = useLanguage();
  const [query, setQuery] = useState('');

  const { chats, isLoading, fetchedAt, ensureLoaded, removeOptimistic } =
    useChatsStore(
      useShallow((s) => ({
        chats: s.chats,
        isLoading: s.isLoading,
        fetchedAt: s.fetchedAt,
        ensureLoaded: s.ensureLoaded,
        removeOptimistic: s.removeOptimistic,
      })),
    );

  const loading = isLoading && fetchedAt === null;

  useEffect(() => {
    ensureLoaded().catch(() => {
      /* handled by store */
    });
  }, [ensureLoaded]);

  const setChats = (next: Chat[]) => {
    const nextIds = new Set(next.map((c) => c.id));
    chats
      .filter((c) => !nextIds.has(c.id))
      .forEach((c) => removeOptimistic(c.id));
  };

  const sortedChats = useMemo(() => {
    const list = query.trim()
      ? chats.filter((c) =>
          (c.title ?? '').toLowerCase().includes(query.toLowerCase()),
        )
      : chats;

    return [...list].sort(
      (a, b) =>
        (new Date(b.createdAt).getTime() || 0) -
        (new Date(a.createdAt).getTime() || 0),
    );
  }, [chats, query]);

  return (
    <div>
      <div className="flex flex-col pt-10 border-b border-light-200/20 dark:border-dark-200/20 pb-6 px-2">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-3">
          <div className="flex items-center justify-center lg:justify-start gap-3">
            <History size={40} className="mb-1 text-black dark:text-white" />
            <div className="flex flex-col">
              <h1
                className="text-4xl lg:text-5xl font-normal p-2 pb-0 text-black dark:text-white"
                style={{ fontFamily: 'PP Editorial, serif' }}
              >
                {app.history.title}
              </h1>
              <div className="px-2 text-sm text-black/60 dark:text-white/60 text-center lg:text-left">
                {app.history.subtitle}
              </div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-2">
            <div className="relative w-full sm:w-64">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-black/40 dark:text-white/40 pointer-events-none"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={app.history.searchPlaceholder}
                className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-light-secondary dark:bg-dark-secondary border border-light-200 dark:border-dark-200 text-sm text-black dark:text-white placeholder:text-black/30 dark:placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-accent/30 transition-all"
              />
            </div>
            <span className="inline-flex items-center gap-1 rounded-full border border-black/20 dark:border-white/20 px-2 py-0.5 text-xs text-black/60 dark:text-white/60 whitespace-nowrap">
              <History size={13} />
              {loading
                ? app.common.loading
                : `${sortedChats.length} ${sortedChats.length === 1 ? 'chat' : 'chats'}`}
            </span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-row items-center justify-center min-h-[60vh]">
          <svg
            aria-hidden="true"
            className="w-8 h-8 text-light-200 fill-light-secondary dark:text-[#202020] animate-spin dark:fill-[#ffffff3b]"
            viewBox="0 0 100 101"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M100 50.5908C100.003 78.2051 78.1951 100.003 50.5908 100C22.9765 99.9972 0.997224 78.018 1 50.4037C1.00281 22.7993 22.8108 0.997224 50.4251 1C78.0395 1.00281 100.018 22.8108 100 50.4251ZM9.08164 50.594C9.06312 73.3997 27.7909 92.1272 50.5966 92.1457C73.4023 92.1642 92.1298 73.4365 92.1483 50.6308C92.1669 27.8251 73.4392 9.0973 50.6335 9.07878C27.8278 9.06026 9.10003 27.787 9.08164 50.594Z"
              fill="currentColor"
            />
            <path
              d="M93.9676 39.0409C96.393 38.4037 97.8624 35.9116 96.9801 33.5533C95.1945 28.8227 92.871 24.3692 90.0681 20.348C85.6237 14.1775 79.4473 9.36872 72.0454 6.45794C64.6435 3.54717 56.3134 2.65431 48.3133 3.89319C45.869 4.27179 44.3768 6.77534 45.014 9.20079C45.6512 11.6262 48.1343 13.0956 50.5786 12.717C56.5073 11.8281 62.5542 12.5399 68.0406 14.7911C73.527 17.0422 78.2187 20.7487 81.5841 25.4923C83.7976 28.5886 85.4467 32.059 86.4416 35.7474C87.1273 38.1189 89.5423 39.6781 91.9676 39.0409Z"
              fill="currentFill"
            />
          </svg>
        </div>
      ) : chats.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[70vh] px-2 text-center">
          <div className="flex items-center justify-center w-12 h-12 rounded-2xl border border-light-200 dark:border-dark-200 bg-light-secondary dark:bg-dark-secondary">
            <History className="text-black/70 dark:text-white/70" />
          </div>
          <p className="mt-2 text-black/70 dark:text-white/70 text-sm">
            {app.history.emptyTitle}
          </p>
          <p className="mt-1 text-black/70 dark:text-white/70 text-sm">
            <Link href="/chat" className="text-sky-400">
              {app.history.startNewSearch}
            </Link>{' '}
            {app.history.emptyDesc}
          </p>
        </div>
      ) : sortedChats.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[30vh] px-2 text-center">
          <p className="text-black/50 dark:text-white/50 text-sm">
            {app.templates.emptyTitle}
          </p>
        </div>
      ) : (
        <div className="pt-6 pb-28 px-2">
          <div className="rounded-2xl border border-light-200 dark:border-dark-200 overflow-hidden bg-light-primary dark:bg-dark-primary">
            {sortedChats.map((chat, index) => {
              const sourcesLabel =
                chat.sources.length === 0
                  ? null
                  : chat.sources.length <= 2
                    ? chat.sources
                        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
                        .join(', ')
                    : `${chat.sources
                        .slice(0, 2)
                        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
                        .join(', ')} + ${chat.sources.length - 2}`;

              return (
                <div
                  key={chat.id}
                  className={
                    'group flex flex-col gap-2 p-4 hover:bg-light-secondary dark:hover:bg-dark-secondary transition-colors duration-200 ' +
                    (index !== sortedChats.length - 1
                      ? 'border-b border-light-200 dark:border-dark-200'
                      : '')
                  }
                >
                  <div className="flex items-start justify-between gap-3">
                    <Link
                      href={`/c/${chat.id}`}
                      className="flex-1 text-black dark:text-white text-base lg:text-lg font-medium leading-snug line-clamp-2 group-hover:text-[#24A0ED] transition duration-200"
                      title={chat.title}
                    >
                      {chat.title}
                    </Link>
                    <div className="pt-0.5 shrink-0">
                      <DeleteChat
                        chatId={chat.id}
                        chats={chats}
                        setChats={setChats}
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-black/70 dark:text-white/70">
                    <span className="inline-flex items-center gap-1 text-xs">
                      <ClockIcon size={14} />
                      {formatTimeDifference(new Date(), chat.createdAt)} Ago
                    </span>

                    {sourcesLabel && (
                      <span className="inline-flex items-center gap-1 text-xs border border-black/20 dark:border-white/20 rounded-full px-2 py-0.5">
                        <Globe2Icon size={14} />
                        {sourcesLabel}
                      </span>
                    )}
                    {chat.files.length > 0 && (
                      <span className="inline-flex items-center gap-1 text-xs border border-black/20 dark:border-white/20 rounded-full px-2 py-0.5">
                        <FileText size={14} />
                        {chat.files.length}{' '}
                        {chat.files.length === 1 ? 'file' : 'files'}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default HistoryView;
