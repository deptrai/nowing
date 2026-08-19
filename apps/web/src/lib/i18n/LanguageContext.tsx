'use client';

import React, { createContext, useContext, useState, useEffect, useMemo, type ReactNode } from 'react';
import { type Language, type AppTranslations, translations } from './translations';
import { type LandingTranslations } from './landingTranslations';

interface LanguageContextType {
  lang: Language;
  setLang: (lang: Language) => void;
  toggleLang: () => void;
  t: LandingTranslations;
  app: AppTranslations;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const STORAGE_KEY = 'chainlens_landing_lang';

export function LanguageProvider({ 
  children, 
  initialLang = 'vi' 
}: { 
  children: ReactNode; 
  initialLang?: Language;
}) {
  const [lang, setLangState] = useState<Language>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem(STORAGE_KEY) as Language | null;
        if (saved === 'en' || saved === 'vi') return saved;
        const browserLang = navigator.language?.toLowerCase() || '';
        if (browserLang.startsWith('vi')) return 'vi';
      } catch {
        // ignore
      }
    }
    return initialLang;
  });

  useEffect(() => {
    const handleStorage = () => {
      try {
        const saved = localStorage.getItem(STORAGE_KEY) as Language | null;
        if (saved === 'en' || saved === 'vi') {
          setLangState(saved);
        }
      } catch {
        // ignore
      }
    };

    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const setLang = (newLang: Language) => {
    setLangState(newLang);
    try {
      localStorage.setItem(STORAGE_KEY, newLang);
      window.dispatchEvent(new Event('storage'));
    } catch {
      // Ignore
    }
  };

  const toggleLang = () => {
    setLang(lang === 'en' ? 'vi' : 'en');
  };

  const app = useMemo(() => translations[lang], [lang]);
  const t = useMemo(() => app.landing, [app]);

  const value = useMemo(() => ({
    lang,
    setLang,
    toggleLang,
    t,
    app,
  }), [lang, t, app]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    return {
      lang: 'vi' as Language,
      setLang: () => {},
      toggleLang: () => {},
      t: translations.vi.landing,
      app: translations.vi,
    };
  }
  return context;
}
