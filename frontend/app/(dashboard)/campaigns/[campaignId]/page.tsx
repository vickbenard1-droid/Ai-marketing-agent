"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  CheckCircle2,
  Loader2,
  Pencil,
  RefreshCw,
  Sparkles,
  Target,
  Users,
  Wallet,
} from "lucide-react";
import {
  ApiError,
  approveCampaign,
  generateCampaign,
  getCampaign,
  updateAdCopyVariant,
  type AdCopyVariantPublic,
  type CampaignDetail,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { ExperimentsPanel } from "@/components/campaigns/experiments-panel";

export default function CampaignDetailPage() {
  const params = useParams<{ campaignId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { accessToken, activeOrganizationId } = useSession();

  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const detail = await getCampaign(accessToken, activeOrganizationId, params.campaignId);
    setCampaign(detail);
    return detail;
  }

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    load()
      .then((detail) => {
        if (searchParams.get("generate") === "1" && detail?.status === "draft") {
          handleGenerate();
        }
      })
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId, params.campaignId]);

  async function handleGenerate() {
    if (!accessToken || !activeOrganizationId) return;
    setError(null);
    setIsGenerating(true);
    try {
      const generated = await generateCampaign(accessToken, activeOrganizationId, params.campaignId);
      setCampaign(generated);
      router.replace(`/campaigns/${params.campaignId}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? String(err.detail ?? "Generation failed — try again")
          : "Generation failed — try again"
      );
      await load();
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleApprove() {
    if (!accessToken || !activeOrganizationId) return;
    setIsApproving(true);
    try {
      await approveCampaign(accessToken, activeOrganizationId, params.campaignId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't approve") : "Couldn't approve");
    } finally {
      setIsApproving(false);
    }
  }

  function handleVariantUpdated(updated: AdCopyVariantPublic) {
    setCampaign((prev) =>
      prev
        ? {
            ...prev,
            ad_copy_variants: prev.ad_copy_variants.map((v) => (v.id === updated.id ? updated : v)),
          }
        : prev
    );
  }

  if (isLoading || !campaign) {
    return (
      <>
        <Header title="Campaign" />
        <main className="flex-1 p-6">
          <p className="text-sm text-ink-500">Loading…</p>
        </main>
      </>
    );
  }

  return (
    <>
      <Header title={campaign.product_name} description={statusLabel(campaign.status)} />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {error && (
            <p role="alert" className="rounded-md bg-signal-soft px-4 py-3 text-sm text-signal">
              {error}
            </p>
          )}

          {campaign.status === "draft" && !isGenerating && (
            <div className="rounded-lg border border-dashed border-ink-200 bg-white p-8 text-center">
              <Sparkles className="mx-auto mb-3 h-8 w-8 text-ink-300" />
              <p className="mb-4 text-sm text-ink-500">This campaign hasn&apos;t been generated yet.</p>
              <Button onClick={handleGenerate} className="gap-1.5">
                <Sparkles className="h-4 w-4" />
                Generate campaign
              </Button>
            </div>
          )}

          {isGenerating && (
            <div className="rounded-lg border border-ink-100 bg-white p-8 text-center">
              <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-ink-400" />
              <p className="text-sm text-ink-500">
                Generating strategy, audience plan, ad copy, and creative concepts…
              </p>
            </div>
          )}

          {campaign.strategy && !isGenerating && (
            <>
              <StrategySection strategy={campaign.strategy} />
              <AudienceSection strategy={campaign.strategy} />
              <AdCopySection
                campaign={campaign}
                variants={campaign.ad_copy_variants}
                onVariantUpdated={handleVariantUpdated}
                canEdit={campaign.status !== "approved"}
              />
              <CreativeSection concepts={campaign.creative_concepts} />
              <BudgetSection strategy={campaign.strategy} />

              <ExperimentsPanel
                campaignId={campaign.id}
                adCopyVariants={campaign.ad_copy_variants}
                creativeConcepts={campaign.creative_concepts}
              />

              <div className="flex items-center justify-between rounded-lg border border-ink-100 bg-white p-5 shadow-panel">
                {campaign.status === "approved" ? (
                  <div className="flex items-center gap-2 text-sm text-positive">
                    <CheckCircle2 className="h-4 w-4" />
                    Approved — nothing has been launched or spent.
                  </div>
                ) : (
                  <>
                    <Button variant="secondary" onClick={handleGenerate} disabled={isGenerating} className="gap-1.5">
                      <RefreshCw className="h-4 w-4" />
                      Regenerate
                    </Button>
                    <Button onClick={handleApprove} disabled={isApproving} className="gap-1.5">
                      <CheckCircle2 className="h-4 w-4" />
                      {isApproving ? "Approving…" : "Approve draft"}
                    </Button>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}

function statusLabel(status: CampaignDetail["status"]): string {
  switch (status) {
    case "draft":
      return "Draft — not yet generated";
    case "generating":
      return "Generating…";
    case "generated":
      return "Ready for review";
    case "approved":
      return "Approved";
  }
}

function SectionCard({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
      <div className="mb-4 flex items-center gap-2">
        <Icon className="h-4 w-4 text-ink-400" />
        <h2 className="text-sm font-semibold text-ink-900">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | number | null }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="border-b border-ink-50 py-2 last:border-0">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
      <p className="mt-0.5 text-sm text-ink-800">{value}</p>
    </div>
  );
}

function ListRow({ label, values }: { label: string; values?: string[] }) {
  if (!values || values.length === 0) return null;
  return (
    <div className="border-b border-ink-50 py-2 last:border-0">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
      <ul className="mt-1 list-disc pl-4">
        {values.map((v, i) => (
          <li key={i} className="text-sm text-ink-800">
            {v}
          </li>
        ))}
      </ul>
    </div>
  );
}

function StrategySection({ strategy }: { strategy: NonNullable<CampaignDetail["strategy"]> }) {
  const s = strategy.strategy;
  return (
    <SectionCard icon={Target} title="Campaign strategy">
      <Row label="Objective" value={s.objective} />
      <Row label="Funnel stage" value={s.funnel_stage} />
      <Row label="Target customer" value={s.target_customer} />
      <ListRow label="Pain points" values={s.pain_points} />
      <Row label="Value proposition" value={s.value_proposition} />
      <Row label="Offer" value={s.offer} />
      <Row label="CTA" value={s.cta} />
    </SectionCard>
  );
}

function AudienceSection({ strategy }: { strategy: NonNullable<CampaignDetail["strategy"]> }) {
  const a = strategy.audience;
  return (
    <SectionCard icon={Users} title="Audience strategy">
      <Row label="Demographics" value={a.demographics} />
      <Row label="Geography" value={a.geography} />
      <ListRow label="Interests" values={a.interests} />
      <ListRow label="Behaviors" values={a.behaviors} />
      <Row label="Lookalike strategy" value={a.lookalike_strategy} />
      <Row label="Retargeting strategy" value={a.retargeting_strategy} />
      <p className="mt-3 text-xs text-ink-400">
        These are recommendations to test, not guarantees — no audience is certain to convert.
      </p>
    </SectionCard>
  );
}

function BudgetSection({ strategy }: { strategy: NonNullable<CampaignDetail["strategy"]> }) {
  const b = strategy.budget_strategy;
  return (
    <SectionCard icon={Wallet} title="Budget strategy">
      <Row label="Test budget" value={b.test_budget} />
      <Row label="Ad set count" value={b.ad_set_count} />
      <Row label="Budget allocation" value={b.budget_allocation} />
      <Row label="Testing period" value={b.testing_period_days ? `${b.testing_period_days} days` : undefined} />
      <Row label="Scaling rules" value={b.scaling_rules} />
    </SectionCard>
  );
}

function CreativeSection({ concepts }: { concepts: CampaignDetail["creative_concepts"] }) {
  if (concepts.length === 0) return null;
  return (
    <SectionCard icon={Sparkles} title="Creative strategy">
      <div className="grid gap-3 sm:grid-cols-2">
        {concepts.map((c) => (
          <div key={c.id} className="rounded-md border border-ink-100 p-3">
            <span className="mb-1 inline-block rounded-sm bg-ink-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-500">
              {c.concept_type.replace(/_/g, " ")}
            </span>
            <p className="text-sm font-medium text-ink-900">{c.title}</p>
            <p className="mt-0.5 text-xs text-ink-500">{c.description}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function AdCopySection({
  campaign,
  variants,
  onVariantUpdated,
  canEdit,
}: {
  campaign: CampaignDetail;
  variants: AdCopyVariantPublic[];
  onVariantUpdated: (v: AdCopyVariantPublic) => void;
  canEdit: boolean;
}) {
  const { accessToken, activeOrganizationId } = useSession();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Partial<AdCopyVariantPublic>>({});
  const [isSaving, setIsSaving] = useState(false);

  if (variants.length === 0) return null;

  function startEdit(v: AdCopyVariantPublic) {
    setEditingId(v.id);
    setDraft({
      headline: v.headline,
      primary_text: v.primary_text,
      description: v.description,
      call_to_action: v.call_to_action,
    });
  }

  async function saveEdit(variantId: string) {
    if (!accessToken || !activeOrganizationId) return;
    setIsSaving(true);
    try {
      const updated = await updateAdCopyVariant(accessToken, activeOrganizationId, campaign.id, variantId, draft);
      onVariantUpdated(updated);
      setEditingId(null);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <SectionCard icon={Pencil} title="Ad copy variants">
      <div className="flex flex-col gap-3">
        {variants.map((v) => (
          <div key={v.id} className="rounded-md border border-ink-100 p-4">
            {editingId === v.id ? (
              <div className="flex flex-col gap-2">
                <input
                  className="rounded border border-ink-200 px-2 py-1.5 text-sm font-medium"
                  value={draft.headline ?? ""}
                  onChange={(e) => setDraft((d) => ({ ...d, headline: e.target.value }))}
                />
                <textarea
                  className="rounded border border-ink-200 px-2 py-1.5 text-sm"
                  rows={2}
                  value={draft.primary_text ?? ""}
                  onChange={(e) => setDraft((d) => ({ ...d, primary_text: e.target.value }))}
                />
                <input
                  className="rounded border border-ink-200 px-2 py-1.5 text-sm"
                  placeholder="Description"
                  value={draft.description ?? ""}
                  onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
                />
                <input
                  className="rounded border border-ink-200 px-2 py-1.5 text-sm"
                  placeholder="CTA"
                  value={draft.call_to_action ?? ""}
                  onChange={(e) => setDraft((d) => ({ ...d, call_to_action: e.target.value }))}
                />
                <div className="mt-1 flex gap-2">
                  <Button onClick={() => saveEdit(v.id)} disabled={isSaving}>
                    {isSaving ? "Saving…" : "Save"}
                  </Button>
                  <Button variant="ghost" onClick={() => setEditingId(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink-900">
                    {v.headline}
                    {v.is_edited && (
                      <span className="ml-2 text-[10px] font-medium uppercase tracking-wide text-ink-400">
                        edited
                      </span>
                    )}
                  </p>
                  <p className="mt-1 text-sm text-ink-700">{v.primary_text}</p>
                  {v.description && <p className="mt-1 text-xs text-ink-500">{v.description}</p>}
                  <span className="mt-2 inline-block rounded-full bg-ink-900 px-2.5 py-0.5 text-xs font-medium text-white">
                    {v.call_to_action}
                  </span>
                </div>
                {canEdit && (
                  <button
                    onClick={() => startEdit(v)}
                    className="shrink-0 rounded-md p-1.5 text-ink-400 hover:bg-ink-50 hover:text-ink-700"
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
