'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useAuth } from '@/lib/hooks/useAuth';
import { ApiKeyCard } from '@/components/Dashboard/ApiKeyCard';
import { ApiKeysTable } from '@/components/Dashboard/ApiKeysTable';
import { CreateApiKeyModal } from '@/components/Dashboard/CreateApiKeyModal';
import { UsageChart } from '@/components/Dashboard/UsageChart';
import { RateLimitCard } from '@/components/Dashboard/RateLimitCard';
import { TeamSettingsCard } from '@/components/Dashboard/TeamSettingsCard';
import { BillingLinkCard } from '@/components/Dashboard/BillingLinkCard';
import { WorkspaceSelector } from '@/components/Dashboard/WorkspaceSelector';
import {
  fetchApiKeys,
  fetchUsageMetrics,
  fetchUserQuota,
  type ApiKeyItem,
  type CreatedApiKeyResponse,
  type QuotaStatusResponse,
  type UsageTimeSeriesResponse,
} from '@/lib/dashboard/api-keys-usage';
import { useLanguage } from '@/lib/i18n/LanguageContext';

export default function DashboardApiKeysPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { app } = useLanguage();

  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [selectedKeyId, setSelectedKeyId] = useState<string | undefined>(undefined);
  const [fullKeyMap, setFullKeyMap] = useState<Record<string, string>>({});
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const [usageRange, setUsageRange] = useState<'7d' | '30d' | '90d'>('30d');
  const [usageData, setUsageData] = useState<UsageTimeSeriesResponse | null>(null);
  const [loadingUsage, setLoadingUsage] = useState(true);

  const [quotaData, setQuotaData] = useState<QuotaStatusResponse | null>(null);

  const loadKeys = useCallback(async () => {
    setLoadingKeys(true);
    try {
      const data = await fetchApiKeys();
      setKeys(data);
      if (data.length > 0) {
        setSelectedKeyId((prev) => (prev && data.some((k) => k.id === prev) ? prev : data[0].id));
      } else {
        setSelectedKeyId(undefined);
      }
    } catch {
      toast.error('Failed to load API keys');
      setKeys([]);
    } finally {
      setLoadingKeys(false);
    }
  }, []);

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
      loadKeys();
      loadUsage(usageRange);
      loadQuota();
    } else {
      setLoadingKeys(false);
      setLoadingUsage(false);
    }
  }, [user, loadKeys, loadUsage, loadQuota, usageRange]);

  useEffect(() => {
    void loadUsage(usageRange);
  }, [usageRange, loadUsage]);

  const handleCreated = (created: CreatedApiKeyResponse) => {
    setFullKeyMap((prev) => ({ ...prev, [created.id]: created.key }));
    setSelectedKeyId(created.id);
    void loadKeys();
  };

  const selectedKey = keys.find((k) => k.id === selectedKeyId) ?? keys[0];

  return (
    <div data-testid="dashboard-api-keys-page" className="flex flex-col gap-6 pb-12">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-black dark:text-white">
            {app.apiKeys.title}
          </h1>
          <p className="text-xs text-black/60 dark:text-white/60 mt-1">
            {app.apiKeys.subtitle}
          </p>
        </div>

        <WorkspaceSelector />
      </div>

      {/* Top Grid: Primary Key Card + Usage Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-1">
          <ApiKeyCard
            keys={keys}
            selectedKey={selectedKey}
            fullKeyMap={fullKeyMap}
            onCreateClick={() => setIsCreateModalOpen(true)}
            className="h-full"
          />
        </div>
        <div className="lg:col-span-2 min-w-0">
          <UsageChart
            data={usageData}
            loading={loadingUsage}
            range={usageRange}
            onRangeChange={setUsageRange}
            className="h-full"
          />
        </div>
      </div>

      {/* Bottom Grid: All Keys Table + Secondary Info Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
        <div className="lg:col-span-2">
          <ApiKeysTable
            keys={keys}
            loading={loadingKeys}
            fullKeyMap={fullKeyMap}
            selectedKeyId={selectedKeyId}
            onSelectKey={(k) => setSelectedKeyId(k.id)}
            onCreateClick={() => setIsCreateModalOpen(true)}
            onRefresh={loadKeys}
          />
        </div>

        <div className="flex flex-col gap-5 lg:col-span-1">
          <RateLimitCard selectedKey={selectedKey} quota={quotaData} />
          <TeamSettingsCard />
          <BillingLinkCard />
        </div>
      </div>

      {/* Create Key Modal */}
      <CreateApiKeyModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  );
}
