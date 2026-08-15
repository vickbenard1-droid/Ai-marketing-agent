"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles, Upload, X } from "lucide-react";
import {
  ApiError,
  CONTENT_TYPE_OPTIONS,
  generateContent,
  uploadContentAsset,
  type ContentAssetWithUrl,
  type ContentType,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { TextareaField } from "@/components/ui/textarea-field";
import { Field } from "@/components/ui/field";

export default function NewContentPage() {
  const router = useRouter();
  const { accessToken, activeOrganizationId } = useSession();

  const [contentType, setContentType] = useState<ContentType | "">("");
  const [sourceText, setSourceText] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [asset, setAsset] = useState<ContentAssetWithUrl | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!accessToken || !activeOrganizationId) return null;

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setIsUploading(true);
    try {
      const uploaded = await uploadContentAsset(accessToken!, activeOrganizationId!, file);
      setAsset(uploaded);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Upload failed") : "Upload failed");
    } finally {
      setIsUploading(false);
      e.target.value = ""; // allow re-selecting the same file later
    }
  }

  async function handleGenerate() {
    if (!contentType) return;
    setError(null);
    setIsGenerating(true);
    try {
      const content = await generateContent(accessToken!, activeOrganizationId!, {
        content_type: contentType,
        source_text: sourceText || null,
        source_url: sourceUrl || null,
        source_asset_id: asset?.id || null,
      });
      router.push(`/content/${content.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? String(err.detail ?? "Generation failed — try again")
          : "Generation failed — try again"
      );
      setIsGenerating(false);
    }
  }

  const canGenerate = !!contentType && !isGenerating && !isUploading;

  return (
    <>
      <Header title="Generate content" description="Provide source material and pick a content type" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-6">
          <div className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
            <p className="mb-3 text-sm font-medium text-ink-700">Content type</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {CONTENT_TYPE_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  onClick={() => setContentType(o.value)}
                  className={`rounded-md border px-3 py-2 text-left text-sm font-medium transition-colors ${
                    contentType === o.value ? "border-ink-900 bg-ink-50" : "border-ink-200 hover:border-ink-400"
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
            <p className="mb-3 text-sm font-medium text-ink-700">Source material</p>
            <div className="flex flex-col gap-4">
              <TextareaField
                label="Text or product information"
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                placeholder="Describe the product, offer, or topic — as much detail as you have"
              />
              <Field
                label="Reference URL (optional)"
                type="url"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://yoursite.com/product"
              />

              <div>
                <p className="mb-1.5 text-sm font-medium text-ink-700">Image (optional)</p>
                {asset ? (
                  <div className="flex items-center gap-3 rounded-md border border-ink-200 p-3">
                    {asset.url && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={asset.url} alt="" className="h-12 w-12 rounded object-cover" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-ink-800">{asset.original_filename}</p>
                      <p className="text-xs text-ink-500">
                        {asset.status === "analyzing"
                          ? "Analyzing…"
                          : asset.ai_description || "No description available"}
                      </p>
                    </div>
                    <button onClick={() => setAsset(null)} className="shrink-0 text-ink-400 hover:text-ink-700">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-ink-300 px-4 py-3 text-sm text-ink-500 hover:border-ink-400">
                    {isUploading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" /> Uploading…
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4" /> Upload an image
                      </>
                    )}
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleFileSelect}
                      disabled={isUploading}
                    />
                  </label>
                )}
              </div>
            </div>
          </div>

          {error && (
            <p role="alert" className="text-sm text-signal">
              {error}
            </p>
          )}

          <Button onClick={handleGenerate} disabled={!canGenerate} className="gap-1.5">
            {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {isGenerating ? "Generating…" : "Generate"}
          </Button>
        </div>
      </main>
    </>
  );
}
