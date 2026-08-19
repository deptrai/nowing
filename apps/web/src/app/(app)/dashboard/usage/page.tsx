'use client';

import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/lib/hooks/useAuth';
import { UsageChart } from '@/components/Dashboard/UsageChart';
import { RateLimitCard } from '@/components/Dashboard/RateLimitCard';
import { BillingLinkCard } from '@/components/Dashboard/BillingLinkCard';
import {
  fetchUsageMetrics,
  fetchUserQuota,
  type UsageTimeSeriesResponse,
  type QuotaStatusResponse,
} from '@/lib/dashboard/api-keys-usage';
import { useLanguage } from '@/lib/i18n/LanguageContext';

export default function DashboardUsagePage() {
  const { user } = useAuth();
  const { app } = useLanguage();
  const [usageRange, setUsageRange] = useState<'7d' | '30d' | '90d'>('30d');
  const [usageData, setUsageData] = useState<UsageTimeSeriesResponse | null>(null);
  const [loadingUsage, setLoadingUsage] = useState(true);
  const [quotaData, setQuotaData] = useState<QuotaStatusResponse | null>(null);

  const loadUsage = useCallback(async (r: '7d' | '30d' | '90d') => {
    setLoadingUsage(true);
    try {
      const data = await fetchUsageMetrics(r);
      setUsageData(data);
    } catch {
      setUsageData(null);
    } finally {
      setLoadingUsage(false);
    }
  }, []);

  const loadQuota = useCallback(async () => {
    try {
      const data = await fetchUserQuota();
      setQuotaData(data);
    } catch {
      setQuotaData(null);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadUsage(usageRange);
      void loadQuota();
    } else {
      setLoadingUsage(false);
    }
  }, [user, loadUsage, loadQuota, usageRange]);

  return (
    <div className="space-y-6 max-w-6xl pb-10">
      <div>
        <h1 className="text-2xl font-bold text-black dark:text-white">
          {app.usage.title}
        </h1>
        <p className="text-xs text-black/50 dark:text-white/50 mt-1">
          {app.usage.subtitle}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <UsageChart
            data={usageData}
            loading={loadingUsage}
            range={usageRange}
            onRangeChange={(r) => {
              setUsageRange(r);
              void loadUsage(r);
            }}
          />
        </div>
        <div className="space-y-4">
          <RateLimitCard quota={quotaData} />
          <BillingLinkCard />
        </div>
      </div>
    </div>
  );
}
