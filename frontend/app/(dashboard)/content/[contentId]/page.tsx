"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle2, Loader2, Save, Search, Trash2 } from "lucide-react";
import {
  ApiError,
  approveContent,
  deleteContentItem,
  generateSEO,
  getContent,
  updateContent,
  type ContentPublic,
  type SEOContentPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

export default function ContentDetailPage() {
  const params = useParams<{ contentId: string }>();
  const router = useRouter();
  const { accessToken, activeOrganizationId } = useSession();

  const [content, setContent] = useState<ContentPublic | null>(null);
  const [body, setBody] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [seo, setSeo] = useState<SEOContentPublic | null>(null);
  const [seoTopic, setSeoTopic] = useState("");
  const [isGeneratingSeo, setIsGeneratingSeo] = useState(false);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    getContent(accessToken, activeOrganizationId, params.contentId)
      .then((detail) => {
        setContent(detail);
        setBody(detail.body);
        setSeoTopic(detail.title || detail.body.slice(0, 80));
      })
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId, params.contentId]);

  async function handleSave() {
    if (!accessToken || !activeOrganizationId || !content) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await updateContent(accessToken, activeOrganizationId, content.id, { body });
      setContent(updated);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't save") : "Couldn't save");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleApprove() {
    if (!accessToken || !activeOrganizationId || !content) return;
    setIsApproving(true);
    try {
      const updated = await approveContent(accessToken, activeOrganizationId, content.id);
      setContent(updated);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't approve") : "Couldn't approve");
    } finally {
      setIsApproving(false);
    }
  }

  async function handleDelete() {
    if (!accessToken || !activeOrganizationId || !content) return;
    setIsDeleting(true);
    try {
      await deleteContentItem(accessToken, activeOrganizationId, content.id);
      router.push("/content");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't delete") : "Couldn't delete");
      setIsDeleting(false);
    }
  }

  async function handleGenerateSeo() {
    if (!accessToken || !activeOrganizationId || !content || !seoTopic.trim()) return;
    setIsGeneratingSeo(true);
    setError(null);
    try {
      const result = await generateSEO(accessToken, activeOrganizationId, {
        topic: seoTopic,
        content_id: content.id,
      });
      setSeo(result);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "SEO generation failed") : "SEO generation failed");
    } finally {
      setIsGeneratingSeo(false);
    }
  }

  if (isLoading || !content) {
    return (
      <>
        <Header title="Content" />
        <main className="flex-1 p-6">
          <p className="text-sm text-ink-500">Loading…</p>
        </main>
      </>
    );
  }

  const isApproved = content.status === "approved";
  const isDirty = body !== content.body;

  return (
    <>
      <Header
        title={content.title || content.content_type.replace(/_/g, " ")}
        description={isApproved ? "Approved" : "Draft"}
      />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {error && (
            <p role="alert" className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">
              {error}
            </p>
          )}

          <div className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              disabled={isApproved}
              rows={12}
              className="w-full resize-y rounded-md border border-ink-200 bg-white p-3 text-sm text-ink-900 focus:border-ink-500 disabled:bg-ink-50 disabled:text-ink-500"
            />

            <div className="mt-4 flex items-center justify-between">
              <div className="flex gap-2">
                {!isApproved && (
                  <Button onClick={handleSave} disabled={!isDirty || isSaving} variant="secondary" className="gap-1.5">
                    <Save className="h-4 w-4" />
                    {isSaving ? "Saving…" : "Save changes"}
                  </Button>
                )}
                {!isApproved && (
                  <Button onClick={handleApprove} disabled={isApproving} className="gap-1.5">
                    <CheckCircle2 className="h-4 w-4" />
                    {isApproving ? "Approving…" : "Approve"}
                  </Button>
                )}
              </div>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-signal hover:bg-signal-soft"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </div>
          </div>

          <div className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
            <div className="mb-3 flex items-center gap-2">
              <Search className="h-4 w-4 text-ink-400" />
              <h2 className="text-sm font-semibold text-ink-900">SEO</h2>
            </div>

            {!seo ? (
              <div className="flex gap-2">
                <input
                  value={seoTopic}
                  onChange={(e) => setSeoTopic(e.target.value)}
                  placeholder="Topic to optimize for"
                  className="flex-1 rounded-md border border-ink-200 px-3 py-2 text-sm"
                />
                <Button onClick={handleGenerateSeo} disabled={isGeneratingSeo || !seoTopic.trim()} className="gap-1.5">
                  {isGeneratingSeo && <Loader2 className="h-4 w-4 animate-spin" />}
                  {isGeneratingSeo ? "Generating…" : "Generate SEO"}
                </Button>
              </div>
            ) : (
              <div className="flex flex-col gap-2 text-sm">
                <SeoRow label="Primary keyword" value={seo.primary_keyword} />
                <SeoRow label="Secondary keywords" value={seo.secondary_keywords?.join(", ")} />
                <SeoRow label="Search intent" value={seo.search_intent} />
                <SeoRow label="SEO title" value={seo.seo_title} />
                <SeoRow label="Meta description" value={seo.meta_description} />
                <SeoRow label="URL slug" value={seo.url_slug} />
                <SeoRow label="H1" value={seo.h1} />
                <SeoRow label="H2 structure" value={seo.h2_structure?.join(" → ")} />
                <SeoRow label="Internal linking" value={seo.internal_linking_suggestions?.join("; ")} />
                <SeoRow label="Image alt text" value={seo.image_alt_text} />
                <SeoRow label="Hashtags" value={seo.hashtags?.join(" ")} />
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}

function SeoRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="border-b border-ink-50 py-1.5 last:border-0">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}: </span>
      <span className="text-ink-800">{value}</span>
    </div>
  );
}
