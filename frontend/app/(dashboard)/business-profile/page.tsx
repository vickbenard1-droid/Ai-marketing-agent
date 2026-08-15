"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  getOnboardingState,
  onboarding,
  getBrandVoice,
  setBrandVoice,
  BRAND_VOICE_OPTIONS,
  type BusinessProfilePublic,
  type BrandVoice,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { TextareaField } from "@/components/ui/textarea-field";

export default function BusinessProfilePage() {
  const { accessToken, activeOrganization, activeOrganizationId } = useSession();
  const [profile, setProfile] = useState<BusinessProfilePublic | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [industry, setIndustry] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [productsServices, setProductsServices] = useState("");
  const [targetCustomers, setTargetCustomers] = useState("");
  const [monthlyBudget, setMonthlyBudget] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    getOnboardingState(accessToken, activeOrganizationId)
      .then((state) => {
        setProfile(state);
        setIndustry(state.industry ?? "");
        setWebsiteUrl(state.website_url ?? "");
        setProductsServices(state.products_services ?? "");
        setTargetCustomers(state.target_customers ?? "");
        setMonthlyBudget(state.monthly_ad_budget != null ? String(state.monthly_ad_budget) : "");
      })
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId]);

  if (!accessToken || !activeOrganizationId) return null;

  const notOnboarded = !isLoading && profile && !profile.onboarding_completed_at;

  async function handleSave() {
    setError(null);
    setSaved(false);
    setIsSaving(true);
    try {
      await onboarding.saveIndustry(accessToken!, activeOrganizationId!, industry);
      await onboarding.saveWebsite(accessToken!, activeOrganizationId!, websiteUrl || null);
      await onboarding.saveProductsServices(accessToken!, activeOrganizationId!, productsServices);
      await onboarding.saveTargetCustomers(accessToken!, activeOrganizationId!, targetCustomers);
      if (monthlyBudget.trim()) {
        await onboarding.saveBudget(accessToken!, activeOrganizationId!, Number(monthlyBudget));
      }
      const refreshed = await getOnboardingState(accessToken!, activeOrganizationId!);
      setProfile(refreshed);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't save") : "Couldn't save");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <>
      <Header title="Business profile" description={activeOrganization?.name} />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-xl">
          {notOnboarded && (
            <div className="mb-6 flex items-center justify-between rounded-lg border border-ink-200 bg-ink-50 p-4">
              <p className="text-sm text-ink-700">You haven&apos;t finished setting up your business yet.</p>
              <Link href="/onboarding">
                <Button variant="secondary">Finish setup</Button>
              </Link>
            </div>
          )}

          <section className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
            {isLoading ? (
              <p className="text-sm text-ink-500">Loading…</p>
            ) : (
              <div className="flex flex-col gap-4">
                <Field
                  label="Industry"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                />
                <Field
                  label="Website"
                  type="url"
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                />
                <TextareaField
                  label="Products & services"
                  value={productsServices}
                  onChange={(e) => setProductsServices(e.target.value)}
                />
                <TextareaField
                  label="Target customers"
                  value={targetCustomers}
                  onChange={(e) => setTargetCustomers(e.target.value)}
                />
                <Field
                  label="Monthly advertising budget (USD)"
                  type="number"
                  min={0}
                  value={monthlyBudget}
                  onChange={(e) => setMonthlyBudget(e.target.value)}
                />

                {profile?.marketing_goal && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-ink-700">Primary marketing goal</span>
                    <p className="text-sm text-ink-500 capitalize">
                      {profile.marketing_goal.replace(/_/g, " ")}
                    </p>
                  </div>
                )}

                {profile?.social_platforms && profile.social_platforms.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-ink-700">Social platforms</span>
                    <p className="text-sm text-ink-500">{profile.social_platforms.join(", ")}</p>
                  </div>
                )}

                {profile?.advertising_platforms && profile.advertising_platforms.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-ink-700">Advertising platforms</span>
                    <p className="text-sm text-ink-500">{profile.advertising_platforms.join(", ")}</p>
                  </div>
                )}

                {error && (
                  <p role="alert" className="text-sm text-signal">
                    {error}
                  </p>
                )}
                {saved && <p className="text-sm text-positive">Saved.</p>}

                <div>
                  <Button onClick={handleSave} disabled={isSaving}>
                    {isSaving ? "Saving…" : "Save changes"}
                  </Button>
                </div>
              </div>
            )}
          </section>

          <BrandVoiceSection />
        </div>
      </main>
    </>
  );
}

function BrandVoiceSection() {
  const { accessToken, activeOrganizationId } = useSession();
  const [brandVoice, setBrandVoiceValue] = useState<BrandVoice | "">("");
  const [customText, setCustomText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;
    getBrandVoice(accessToken, activeOrganizationId)
      .then((profile) => {
        setBrandVoiceValue(profile.brand_voice ?? "");
        setCustomText(profile.brand_voice_custom ?? "");
      })
      .finally(() => setIsLoading(false));
  }, [accessToken, activeOrganizationId]);

  async function handleSave() {
    if (!accessToken || !activeOrganizationId || !brandVoice) return;
    setError(null);
    setSaved(false);
    setIsSaving(true);
    try {
      await setBrandVoice(accessToken, activeOrganizationId, {
        brand_voice: brandVoice,
        brand_voice_custom: brandVoice === "custom" ? customText : null,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? "Couldn't save") : "Couldn't save");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
      <h2 className="mb-1 text-sm font-semibold text-ink-900">Brand voice</h2>
      <p className="mb-4 text-sm text-ink-500">
        Shapes the tone of everything the AI generates — content, ad copy, and campaigns.
      </p>

      {isLoading ? (
        <p className="text-sm text-ink-500">Loading…</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {BRAND_VOICE_OPTIONS.map((o) => (
              <button
                key={o.value}
                onClick={() => {
                  setBrandVoiceValue(o.value);
                  setSaved(false);
                }}
                className={`rounded-md border px-3 py-2 text-sm font-medium ${
                  brandVoice === o.value ? "border-ink-900 bg-ink-50" : "border-ink-200 hover:border-ink-400"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>

          {brandVoice === "custom" && (
            <TextareaField
              label="Describe your brand voice"
              value={customText}
              onChange={(e) => {
                setCustomText(e.target.value);
                setSaved(false);
              }}
              placeholder="e.g. Quirky and full of puns, talks like a knowledgeable friend"
            />
          )}

          {error && (
            <p role="alert" className="text-sm text-signal">
              {error}
            </p>
          )}
          {saved && <p className="text-sm text-positive">Saved.</p>}

          <div>
            <Button onClick={handleSave} disabled={isSaving || !brandVoice}>
              {isSaving ? "Saving…" : "Save brand voice"}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
