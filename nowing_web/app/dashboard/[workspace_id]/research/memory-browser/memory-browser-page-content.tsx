"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import type { MemoryBrowserListItem, MemoryBrowserDetailResponse } from "@/contracts/types/memory-browser.types";
import { memoryBrowserApiService } from "@/lib/apis/memory-browser-api.service";
import { usePermissionGate } from "@/atoms/members/members-query.atoms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface MemoryBrowserPageContentProps {
  workspaceId: number;
}

export function MemoryBrowserPageContent({ workspaceId }: MemoryBrowserPageContentProps) {
  const t = useTranslations("MemoryBrowser");
  const [items, setItems] = useState<MemoryBrowserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [keyword, setKeyword] = useState("");
  const [selected, setSelected] = useState<MemoryBrowserDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canUpdateMemory = usePermissionGate("memory:update");

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await memoryBrowserApiService.listMemories(workspaceId, {
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, page, pageSize, keyword, t]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const handleView = async (memoryId: number) => {
    try {
      const detail = await memoryBrowserApiService.getMemoryDetail(workspaceId, memoryId);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    }
  };

  const handleFlag = async (memoryId: number, flagReason: string) => {
    try {
      await memoryBrowserApiService.flagForReview(workspaceId, memoryId, flagReason);
      fetchList();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 mb-4">
            <Input
              placeholder={t("searchPlaceholder")}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchList()}
            />
            <Button onClick={fetchList} disabled={loading}>
              {t("search")}
            </Button>
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <div className="rounded-md border">
            <table className="min-w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-2 text-left">{t("content")}</th>
                  <th className="px-4 py-2 text-left">{t("source")}</th>
                  <th className="px-4 py-2 text-left">{t("confidence")}</th>
                  <th className="px-4 py-2 text-left">{t("created")}</th>
                  <th className="px-4 py-2 text-left">{t("versions")}</th>
                  <th className="px-4 py-2 text-left">{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-t">
                    <td className="px-4 py-2">{item.content_snippet}</td>
                    <td className="px-4 py-2">
                      {item.source_url ? (
                        <a href={item.source_url} className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
                          {item.source_type}
                        </a>
                      ) : (
                        item.source_type
                      )}
                    </td>
                    <td className="px-4 py-2">{item.confidence ?? "—"}</td>
                    <td className="px-4 py-2">{format(new Date(item.created_at), "MMM d, yyyy")}</td>
                    <td className="px-4 py-2">{item.version_count}</td>
                    <td className="px-4 py-2 space-x-2">
                      <Button size="sm" variant="outline" onClick={() => handleView(item.id)}>
                        {t("view")}
                      </Button>
                      {canUpdateMemory && (
                        <Button size="sm" variant="secondary" onClick={() => handleFlag(item.id, "Flagged for review")}>
                          {t("flag")}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-muted-foreground">
              {t("showing")} {items.length} / {total}
            </p>
            <div className="space-x-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                {t("previous")}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={page * pageSize >= total}
                onClick={() => setPage(page + 1)}
              >
                {t("next")}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {selected && (
        <Dialog open onOpenChange={(open) => !open && setSelected(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{t("detailTitle")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 text-sm">
              <p>{selected.content}</p>
              {selected.research_thread && (
                <div>
                  <h4 className="font-semibold">{t("researchThread")}</h4>
                  <p>{selected.research_thread.title}</p>
                </div>
              )}
              {selected.versions.length > 0 && (
                <div>
                  <h4 className="font-semibold">{t("versions")}</h4>
                  <ul className="list-disc pl-5">
                    {selected.versions.map((v, idx) => (
                      <li key={idx}>
                        {v.previous_content} → {v.corrected_content}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {selected.relations.length > 0 && (
                <div>
                  <h4 className="font-semibold">{t("relations")}</h4>
                  <div className="flex flex-wrap gap-2">
                    {selected.relations.map((r) => (
                      <Badge key={r.to_memory_id} variant="outline">
                        {r.relation_type} → {r.to_memory_id}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
