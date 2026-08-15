"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Plus } from "lucide-react";
import {
  ApiError,
  createExperiment,
  listExperiments,
  type AdCopyVariantPublic,
  type CreativeConceptPublic,
  type ExperimentDimension,
  type ExperimentPublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";

const DIMENSIONS: { value: ExperimentDimension; label: string }[] = [
  { value: "headline", label: "Headline" },
  { value: "hook", label: "Hook" },
  { value: "creative", label: "Creative" },
  { value: "audience", label: "Audience" },
];

interface ExperimentsPanelProps {
  campaignId: string;
  adCopyVariants: AdCopyVariantPublic[];
  creativeConcepts: CreativeConceptPublic[];
}

export function ExperimentsPanel({ campaignId, adCopyVariants, creativeConcepts }: ExperimentsPanelProps) {
  const { accessToken, activeOrganizationId } = useSession();
  const [experiments, setExperiments] = useState<ExperimentPublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  const [name, setName] = useState("");
  const [dimension, setDimension] = useState<ExperimentDimension>("headline");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [audienceInputs, setAudienceInputs] = useState(["", ""]);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    listExperiments(accessToken, activeOrganizationId, campaignId)
      .then(setExperiments)
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId, campaignId]);

  const candidatePool =
    dimension === "creative"
      ? creativeConcepts
      : dimension === "headline"
        ? adCopyVariants
        : [...adCopyVariants, ...creativeConcepts];

  function toggleId(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]));
  }

  async function handleCreate() {
    if (!accessToken || !activeOrganizationId) return;
    setError(null);

    const variantIds = dimension === "audience" ? audienceInputs.filter((v) => v.trim()) : selectedIds;
    if (!name.trim() || variantIds.length < 2) {
      setError("Give the experiment a name and select at least 2 variants to test.");
      return;
    }

    setIsSaving(true);
    try {
      const created = await createExperiment(accessToken, activeOrganizationId, campaignId, {
        name,
        dimension,
        variant_ids: variantIds,
      });
      setExperiments((prev) => [...prev, created]);
      setIsCreating(false);
      setName("");
      setSelectedIds([]);
      setAudienceInputs(["", ""]);
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail ?? "Couldn't create experiment") : "Couldn't create experiment"
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-ink-400" />
          <h2 className="text-sm font-semibold text-ink-900">A/B test experiments</h2>
        </div>
        {!isCreating && (
          <Button variant="secondary" onClick={() => setIsCreating(true)} className="gap-1.5">
            <Plus className="h-4 w-4" />
            New experiment
          </Button>
        )}
      </div>

      {isLoading ? (
        <p className="text-sm text-ink-500">Loading…</p>
      ) : (
        <>
          {experiments.length === 0 && !isCreating && (
            <p className="text-sm text-ink-500">
              No experiments yet. Test multiple headlines, hooks, creatives, or audiences against each other.
            </p>
          )}

          <div className="flex flex-col gap-2">
            {experiments.map((exp) => (
              <div key={exp.id} className="rounded-md border border-ink-100 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-ink-900">{exp.name}</p>
                  <span className="rounded-full bg-ink-50 px-2 py-0.5 text-xs text-ink-500">{exp.dimension}</span>
                </div>
                <p className="mt-1 text-xs text-ink-500">{exp.variant_ids.length} variants</p>
              </div>
            ))}
          </div>

          {isCreating && (
            <div className="mt-4 rounded-md border border-ink-100 bg-ink-50 p-4">
              <div className="mb-3">
                <Field
                  label="Experiment name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Headline test"
                />
              </div>
              <div className="mb-3 flex flex-col gap-1.5">
                <span className="text-sm font-medium text-ink-700">Testing dimension</span>
                <div className="flex flex-wrap gap-2">
                  {DIMENSIONS.map((d) => (
                    <button
                      key={d.value}
                      onClick={() => {
                        setDimension(d.value);
                        setSelectedIds([]);
                      }}
                      className={`rounded-full border px-3 py-1 text-sm ${
                        dimension === d.value ? "border-ink-900 bg-ink-900 text-white" : "border-ink-200 text-ink-700"
                      }`}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
              </div>

              {dimension === "audience" ? (
                <div className="mb-3 flex flex-col gap-2">
                  <span className="text-sm font-medium text-ink-700">Audience variants to test</span>
                  {audienceInputs.map((val, i) => (
                    <input
                      key={i}
                      className="rounded border border-ink-200 px-2 py-1.5 text-sm"
                      placeholder={`Audience variant ${i + 1}`}
                      value={val}
                      onChange={(e) =>
                        setAudienceInputs((prev) => prev.map((v, idx) => (idx === i ? e.target.value : v)))
                      }
                    />
                  ))}
                  <button
                    onClick={() => setAudienceInputs((prev) => [...prev, ""])}
                    className="self-start text-xs font-medium text-ink-600 hover:underline"
                  >
                    + Add another
                  </button>
                </div>
              ) : (
                <div className="mb-3 flex flex-col gap-2">
                  <span className="text-sm font-medium text-ink-700">Select at least 2 to test</span>
                  {candidatePool.length === 0 && (
                    <p className="text-xs text-ink-400">No candidates available for this dimension yet.</p>
                  )}
                  {candidatePool.map((item) => (
                    <label key={item.id} className="flex items-center gap-2 text-sm text-ink-700">
                      <input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggleId(item.id)} />
                      {"headline" in item ? item.headline : item.title}
                    </label>
                  ))}
                </div>
              )}

              {error && <p className="mb-2 text-sm text-signal">{error}</p>}

              <div className="flex gap-2">
                <Button onClick={handleCreate} disabled={isSaving}>
                  {isSaving ? "Creating…" : "Create experiment"}
                </Button>
                <Button variant="ghost" onClick={() => setIsCreating(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
