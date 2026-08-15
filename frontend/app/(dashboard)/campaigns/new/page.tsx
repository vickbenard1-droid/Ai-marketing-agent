"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Sparkles } from "lucide-react";
import { ApiError, createCampaign, type MarketingGoal } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { TextareaField } from "@/components/ui/textarea-field";

const TOTAL_STEPS = 7; // Business, Product, Objective, Audience, Budget, Creative, Review — Approval happens on the detail page after generation

const OBJECTIVES: { value: MarketingGoal; label: string }[] = [
  { value: "sales", label: "Sales" },
  { value: "leads", label: "Leads" },
  { value: "website_traffic", label: "Website traffic" },
  { value: "brand_awareness", label: "Brand awareness" },
];

export default function NewCampaignPage() {
  const router = useRouter();
  const { accessToken, activeOrganization, activeOrganizationId } = useSession();

  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [productName, setProductName] = useState("");
  const [productPrice, setProductPrice] = useState("");
  const [productDescription, setProductDescription] = useState("");
  const [objective, setObjective] = useState<MarketingGoal | "">("");
  const [desiredOutcomeCount, setDesiredOutcomeCount] = useState("");
  const [targetLocation, setTargetLocation] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [existingCustomerInfo, setExistingCustomerInfo] = useState("");
  const [budgetAmount, setBudgetAmount] = useState("");
  const [budgetCurrency, setBudgetCurrency] = useState("USD");
  const [durationDays, setDurationDays] = useState("");
  const [landingPageUrl, setLandingPageUrl] = useState("");

  if (!accessToken || !activeOrganizationId) return null;

  function goBack() {
    setError(null);
    if (step > 1) setStep(step - 1);
  }

  async function handleNext() {
    setError(null);
    if (step < TOTAL_STEPS) {
      setStep(step + 1);
      return;
    }

    // Final step: create the draft, then go to the detail page where
    // generation is triggered and progress/results are shown.
    setIsSubmitting(true);
    try {
      const created = await createCampaign(accessToken!, activeOrganizationId!, {
        product_name: productName,
        product_price: productPrice ? Number(productPrice) : null,
        product_description: productDescription || null,
        objective: objective as MarketingGoal,
        desired_outcome_count: desiredOutcomeCount ? Number(desiredOutcomeCount) : null,
        target_location: targetLocation || null,
        target_audience: targetAudience || null,
        existing_customer_info: existingCustomerInfo || null,
        budget_amount: budgetAmount ? Number(budgetAmount) : null,
        budget_currency: budgetCurrency,
        duration_days: durationDays ? Number(durationDays) : null,
        landing_page_url: landingPageUrl || null,
      });
      router.push(`/campaigns/${created.id}?generate=1`);
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail ?? "Couldn't save — try again") : "Couldn't save — try again"
      );
      setIsSubmitting(false);
    }
  }

  const canProceed = isStepValid(step, { productName, objective });

  return (
    <>
      <div className="border-b border-ink-100 bg-white px-6 py-4">
        <h1 className="text-base font-semibold text-ink-900">New campaign</h1>
        <p className="text-sm text-ink-500">{activeOrganization?.name}</p>
      </div>
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl">
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
              <StepShell
                title="Business"
                body={`Generating this campaign for ${activeOrganization?.name ?? "your business"}.`}
              >
                <p className="text-sm text-ink-500">
                  We&apos;ll use your business profile — industry, products, and target customers — to
                  ground the AI&apos;s recommendations. You can update that anytime from Business Profile.
                </p>
              </StepShell>
            )}

            {step === 2 && (
              <StepShell title="What are you selling?" body="Describe the specific product or service for this campaign.">
                <div className="flex flex-col gap-4">
                  <Field
                    label="Product or service"
                    required
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    placeholder="e.g. School admission forms"
                  />
                  <Field
                    label="Price (optional)"
                    type="number"
                    min={0}
                    value={productPrice}
                    onChange={(e) => setProductPrice(e.target.value)}
                    placeholder="5000"
                  />
                  <TextareaField
                    label="Description (optional)"
                    value={productDescription}
                    onChange={(e) => setProductDescription(e.target.value)}
                    placeholder="Any details that would help the AI understand what's being sold"
                  />
                </div>
              </StepShell>
            )}

            {step === 3 && (
              <StepShell title="What's the objective?" body="What should this campaign accomplish?">
                <div className="grid grid-cols-2 gap-3">
                  {OBJECTIVES.map((o) => (
                    <button
                      key={o.value}
                      type="button"
                      onClick={() => setObjective(o.value)}
                      className={`rounded-lg border p-4 text-left text-sm font-semibold transition-colors ${
                        objective === o.value ? "border-ink-900 bg-ink-50" : "border-ink-200 hover:border-ink-400"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
                <div className="mt-4">
                  <Field
                    label={`Desired ${objective || "outcome"} count (optional)`}
                    type="number"
                    min={0}
                    value={desiredOutcomeCount}
                    onChange={(e) => setDesiredOutcomeCount(e.target.value)}
                    placeholder="e.g. 100"
                  />
                </div>
              </StepShell>
            )}

            {step === 4 && (
              <StepShell title="Who's the audience?" body="Tell us who you're trying to reach — as much or little as you know.">
                <div className="flex flex-col gap-4">
                  <Field
                    label="Target location (optional)"
                    value={targetLocation}
                    onChange={(e) => setTargetLocation(e.target.value)}
                    placeholder="e.g. Lagos, Nigeria"
                  />
                  <TextareaField
                    label="Target audience (optional)"
                    value={targetAudience}
                    onChange={(e) => setTargetAudience(e.target.value)}
                    placeholder="Who are you trying to reach?"
                  />
                  <TextareaField
                    label="Existing customer information (optional)"
                    value={existingCustomerInfo}
                    onChange={(e) => setExistingCustomerInfo(e.target.value)}
                    placeholder="Anything you know about your current customers"
                  />
                </div>
              </StepShell>
            )}

            {step === 5 && (
              <StepShell title="What's the budget?" body="Your total budget and campaign duration.">
                <div className="flex flex-col gap-4">
                  <div className="flex gap-3">
                    <div className="flex-1">
                      <Field
                        label="Budget"
                        type="number"
                        min={0}
                        value={budgetAmount}
                        onChange={(e) => setBudgetAmount(e.target.value)}
                        placeholder="300000"
                      />
                    </div>
                    <div className="w-28">
                      <Field
                        label="Currency"
                        value={budgetCurrency}
                        onChange={(e) => setBudgetCurrency(e.target.value.toUpperCase())}
                        maxLength={3}
                      />
                    </div>
                  </div>
                  <Field
                    label="Campaign duration (days, optional)"
                    type="number"
                    min={1}
                    value={durationDays}
                    onChange={(e) => setDurationDays(e.target.value)}
                    placeholder="30"
                  />
                </div>
              </StepShell>
            )}

            {step === 6 && (
              <StepShell title="Creative input" body="Optional — where should traffic go?">
                <Field
                  label="Landing page URL (optional)"
                  type="url"
                  value={landingPageUrl}
                  onChange={(e) => setLandingPageUrl(e.target.value)}
                  placeholder="https://yoursite.com/apply"
                />
              </StepShell>
            )}

            {step === 7 && (
              <StepShell
                title="Ready to generate"
                body="AI will build a complete campaign strategy, audience plan, ad copy, creative concepts, and budget plan from what you've entered."
              >
                <div className="rounded-md bg-ink-50 p-4 text-sm text-ink-700">
                  <p className="mb-2 font-medium text-ink-900">{productName}</p>
                  <p>Objective: {objective.replace(/_/g, " ")}</p>
                  {budgetAmount && (
                    <p>
                      Budget: {Number(budgetAmount).toLocaleString()} {budgetCurrency}
                    </p>
                  )}
                  {desiredOutcomeCount && (
                    <p>
                      Target: {desiredOutcomeCount} {objective}
                    </p>
                  )}
                </div>
                <p className="mt-4 text-xs text-ink-400">
                  You&apos;ll be able to review and edit everything the AI generates before approving.
                  Nothing is launched or spent automatically.
                </p>
              </StepShell>
            )}

            {error && (
              <p role="alert" className="mt-4 text-sm text-signal">
                {error}
              </p>
            )}

            <div className="mt-8 flex items-center justify-between">
              <Button variant="ghost" onClick={goBack} disabled={step === 1 || isSubmitting} className="gap-1.5">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
              <Button onClick={handleNext} disabled={!canProceed || isSubmitting} className="gap-1.5">
                {isSubmitting ? (
                  "Creating…"
                ) : step === TOTAL_STEPS ? (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Generate campaign
                  </>
                ) : (
                  <>
                    Next
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}

function StepShell({ title, body, children }: { title: string; body: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold text-ink-900">{title}</h2>
      <p className="mb-6 text-sm text-ink-500">{body}</p>
      {children}
    </div>
  );
}

function isStepValid(step: number, values: { productName: string; objective: string }): boolean {
  switch (step) {
    case 2:
      return values.productName.trim().length > 0;
    case 3:
      return values.objective.trim().length > 0;
    default:
      return true; // steps 1, 4, 5, 6, 7 have no hard requirement beyond earlier steps
  }
}
