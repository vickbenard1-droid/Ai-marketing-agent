"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import {
  ApiError,
  getOnboardingState,
  onboarding,
  updateCurrentOrganization,
  type BusinessProfilePublic,
  type MarketingGoal,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { TextareaField } from "@/components/ui/textarea-field";
import { ChipMultiSelect } from "@/components/ui/chip-multi-select";

const TOTAL_STEPS = 10;

const MARKETING_GOALS: { value: MarketingGoal; label: string; body: string }[] = [
  { value: "sales", label: "Sales", body: "Drive purchases and revenue" },
  { value: "leads", label: "Leads", body: "Collect contact info from prospects" },
  { value: "website_traffic", label: "Website traffic", body: "Get more people to your site" },
  { value: "brand_awareness", label: "Brand awareness", body: "Build recognition and reach" },
];

const SOCIAL_PLATFORM_OPTIONS = [
  { value: "instagram", label: "Instagram" },
  { value: "facebook", label: "Facebook" },
  { value: "tiktok", label: "TikTok" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "youtube", label: "YouTube" },
  { value: "x", label: "X (Twitter)" },
  { value: "pinterest", label: "Pinterest" },
  { value: "none", label: "None yet" },
];

const ADVERTISING_PLATFORM_OPTIONS = [
  { value: "meta_ads", label: "Meta Ads" },
  { value: "google_ads", label: "Google Ads" },
  { value: "tiktok_ads", label: "TikTok Ads" },
  { value: "linkedin_ads", label: "LinkedIn Ads" },
  { value: "youtube", label: "YouTube Ads" },
  { value: "none", label: "None yet" },
];

const COUNTRY_OPTIONS = [
  { code: "US", label: "United States" },
  { code: "CA", label: "Canada" },
  { code: "GB", label: "United Kingdom" },
  { code: "AU", label: "Australia" },
  { code: "DE", label: "Germany" },
  { code: "FR", label: "France" },
  { code: "IN", label: "India" },
  { code: "BR", label: "Brazil" },
  { code: "MX", label: "Mexico" },
  { code: "JP", label: "Japan" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { accessToken, activeOrganization, activeOrganizationId, refreshOrganizations } = useSession();

  const [step, setStep] = useState(1);
  const [isLoadingState, setIsLoadingState] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local form state for every step — kept flat rather than nested per
  // step since most fields are independent and this is simpler to reason
  // about for a 10-step wizard.
  const [businessName, setBusinessName] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [industry, setIndustry] = useState("");
  const [country, setCountry] = useState("");
  const [productsServices, setProductsServices] = useState("");
  const [targetCustomers, setTargetCustomers] = useState("");
  const [marketingGoal, setMarketingGoal] = useState<MarketingGoal | "">("");
  const [monthlyBudget, setMonthlyBudget] = useState("");
  const [socialPlatforms, setSocialPlatforms] = useState<string[]>([]);
  const [advertisingPlatforms, setAdvertisingPlatforms] = useState<string[]>([]);

  // Hydrate from whatever's already saved (resuming a partially-completed
  // onboarding) once we know which org we're onboarding.
  useEffect(() => {
    if (!accessToken || !activeOrganizationId) return;

    setBusinessName(activeOrganization?.name ?? "");

    (async () => {
      try {
        const state: BusinessProfilePublic = await getOnboardingState(accessToken, activeOrganizationId);
        setWebsiteUrl(state.website_url ?? "");
        setIndustry(state.industry ?? "");
        setCountry(state.country ?? "");
        setProductsServices(state.products_services ?? "");
        setTargetCustomers(state.target_customers ?? "");
        setMarketingGoal(state.marketing_goal ?? "");
        setMonthlyBudget(state.monthly_ad_budget != null ? String(state.monthly_ad_budget) : "");
        setSocialPlatforms(state.social_platforms ?? []);
        setAdvertisingPlatforms(state.advertising_platforms ?? []);
        setStep(Math.min(state.onboarding_current_step, TOTAL_STEPS));
        if (state.onboarding_completed_at) {
          router.replace("/dashboard");
        }
      } catch {
        // If this fails, just start fresh at step 1 rather than blocking
        // the whole flow.
      } finally {
        setIsLoadingState(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId]);

  if (isLoadingState || !activeOrganizationId || !accessToken) {
    return <p className="text-sm text-ink-500">Loading…</p>;
  }

  async function goNext(save: () => Promise<unknown>) {
    setError(null);
    setIsSaving(true);
    try {
      await save();
      if (step < TOTAL_STEPS) {
        setStep(step + 1);
      } else {
        await onboarding.complete(accessToken!, activeOrganizationId!);
        router.push("/dashboard");
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail ?? "Couldn't save — try again") : "Couldn't save — try again"
      );
    } finally {
      setIsSaving(false);
    }
  }

  function goBack() {
    setError(null);
    if (step > 1) setStep(step - 1);
  }

  return (
    <div>
      <div className="mb-8">
        <div className="mb-2 flex items-center justify-between text-xs font-medium text-ink-400">
          <span>
            Step {step} of {TOTAL_STEPS}
          </span>
          <span>{Math.round((step / TOTAL_STEPS) * 100)}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
          <div
            className="h-full rounded-full bg-ink-900 transition-all"
            style={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
          />
        </div>
      </div>

      <div className="rounded-lg border border-ink-100 bg-white p-8 shadow-panel">
        {step === 1 && (
          <StepShell title="What's your business called?" body="This is the name we'll use across your account.">
            <Field
              label="Business name"
              required
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              placeholder="Acme Marketing Co."
            />
          </StepShell>
        )}

        {step === 2 && (
          <StepShell title="What's your website?" body="Optional — you can add this later if you don't have one yet.">
            <Field
              label="Website"
              type="url"
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
              placeholder="https://acme.com"
            />
          </StepShell>
        )}

        {step === 3 && (
          <StepShell title="What industry are you in?" body="Helps us tailor recommendations to your market.">
            <Field
              label="Industry"
              required
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g. E-commerce, SaaS, Retail"
            />
          </StepShell>
        )}

        {step === 4 && (
          <StepShell title="Where's your business based?" body="Your primary country of operation.">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="country" className="text-sm font-medium text-ink-700">
                Country
              </label>
              <select
                id="country"
                required
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="rounded-md border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-ink-500"
              >
                <option value="" disabled>
                  Select a country
                </option>
                {COUNTRY_OPTIONS.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
          </StepShell>
        )}

        {step === 5 && (
          <StepShell title="What do you sell?" body="Briefly describe your products or services.">
            <TextareaField
              label="Products & services"
              required
              value={productsServices}
              onChange={(e) => setProductsServices(e.target.value)}
              placeholder="e.g. Handmade candles and home fragrance products"
            />
          </StepShell>
        )}

        {step === 6 && (
          <StepShell title="Who are your target customers?" body="Describe who you're trying to reach.">
            <TextareaField
              label="Target customers"
              required
              value={targetCustomers}
              onChange={(e) => setTargetCustomers(e.target.value)}
              placeholder="e.g. Home decor shoppers aged 25-45 who value sustainable products"
            />
          </StepShell>
        )}

        {step === 7 && (
          <StepShell title="What's your primary marketing goal?" body="We'll prioritize this across your campaigns.">
            <div className="grid grid-cols-2 gap-3">
              {MARKETING_GOALS.map((goal) => (
                <button
                  key={goal.value}
                  type="button"
                  onClick={() => setMarketingGoal(goal.value)}
                  className={`rounded-lg border p-4 text-left transition-colors ${
                    marketingGoal === goal.value
                      ? "border-ink-900 bg-ink-50"
                      : "border-ink-200 hover:border-ink-400"
                  }`}
                >
                  <p className="text-sm font-semibold text-ink-900">{goal.label}</p>
                  <p className="mt-0.5 text-xs text-ink-500">{goal.body}</p>
                </button>
              ))}
            </div>
          </StepShell>
        )}

        {step === 8 && (
          <StepShell
            title="What's your monthly advertising budget?"
            body="A rough number is fine — you can change this anytime."
          >
            <Field
              label="Monthly budget (USD)"
              type="number"
              min={0}
              required
              value={monthlyBudget}
              onChange={(e) => setMonthlyBudget(e.target.value)}
              placeholder="5000"
            />
          </StepShell>
        )}

        {step === 9 && (
          <StepShell title="Which social platforms do you use?" body="Select all that apply.">
            <ChipMultiSelect
              label="Social platforms"
              options={SOCIAL_PLATFORM_OPTIONS}
              selected={socialPlatforms}
              onChange={setSocialPlatforms}
            />
          </StepShell>
        )}

        {step === 10 && (
          <StepShell title="Which advertising platforms do you use?" body="Select all that apply.">
            <ChipMultiSelect
              label="Advertising platforms"
              options={ADVERTISING_PLATFORM_OPTIONS}
              selected={advertisingPlatforms}
              onChange={setAdvertisingPlatforms}
            />
          </StepShell>
        )}

        {error && (
          <p role="alert" className="mt-4 text-sm text-signal">
            {error}
          </p>
        )}

        <div className="mt-8 flex items-center justify-between">
          <Button variant="ghost" onClick={goBack} disabled={step === 1 || isSaving} className="gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>

          <Button
            disabled={
              isSaving ||
              !isStepValid(step, {
                businessName,
                industry,
                country,
                productsServices,
                targetCustomers,
                marketingGoal,
                monthlyBudget,
              })
            }
            onClick={() =>
              goNext(async () => {
                switch (step) {
                  case 1:
                    await updateCurrentOrganization(accessToken!, activeOrganizationId!, {
                      name: businessName,
                    });
                    await refreshOrganizations();
                    return;
                  case 2:
                    return onboarding.saveWebsite(accessToken!, activeOrganizationId!, websiteUrl || null);
                  case 3:
                    return onboarding.saveIndustry(accessToken!, activeOrganizationId!, industry);
                  case 4:
                    return onboarding.saveCountry(accessToken!, activeOrganizationId!, country);
                  case 5:
                    return onboarding.saveProductsServices(
                      accessToken!,
                      activeOrganizationId!,
                      productsServices
                    );
                  case 6:
                    return onboarding.saveTargetCustomers(
                      accessToken!,
                      activeOrganizationId!,
                      targetCustomers
                    );
                  case 7:
                    return onboarding.saveMarketingGoal(
                      accessToken!,
                      activeOrganizationId!,
                      marketingGoal as MarketingGoal
                    );
                  case 8:
                    return onboarding.saveBudget(accessToken!, activeOrganizationId!, Number(monthlyBudget));
                  case 9:
                    return onboarding.saveSocialPlatforms(accessToken!, activeOrganizationId!, socialPlatforms);
                  case 10:
                    return onboarding.saveAdvertisingPlatforms(
                      accessToken!,
                      activeOrganizationId!,
                      advertisingPlatforms
                    );
                }
              })
            }
            className="gap-1.5"
          >
            {isSaving ? "Saving…" : step === TOTAL_STEPS ? "Finish" : "Next"}
            {!isSaving &&
              (step === TOTAL_STEPS ? <Check className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />)}
          </Button>
        </div>
      </div>
    </div>
  );
}

function StepShell({ title, body, children }: { title: string; body: string; children: React.ReactNode }) {
  return (
    <div>
      <h1 className="mb-1 text-lg font-semibold text-ink-900">{title}</h1>
      <p className="mb-6 text-sm text-ink-500">{body}</p>
      {children}
    </div>
  );
}

function isStepValid(
  step: number,
  values: {
    businessName: string;
    industry: string;
    country: string;
    productsServices: string;
    targetCustomers: string;
    marketingGoal: string;
    monthlyBudget: string;
  }
): boolean {
  switch (step) {
    case 1:
      return values.businessName.trim().length > 0;
    case 2:
      return true; // website is optional
    case 3:
      return values.industry.trim().length > 0;
    case 4:
      return values.country.trim().length === 2;
    case 5:
      return values.productsServices.trim().length > 0;
    case 6:
      return values.targetCustomers.trim().length > 0;
    case 7:
      return values.marketingGoal.trim().length > 0;
    case 8:
      return values.monthlyBudget.trim().length > 0 && Number(values.monthlyBudget) >= 0;
    default:
      return true; // steps 9-10 (multi-select) are always valid, even with zero selections
  }
}
