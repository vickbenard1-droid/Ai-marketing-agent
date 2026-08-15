/**
 * Thin fetch wrapper around the backend API.
 *
 * Deliberately not using a generated client this week — the API surface is
 * tiny (auth + organizations). Revisit with an OpenAPI-generated client
 * once more endpoints exist.
 *
 * NEXT_PUBLIC_API_URL is the only backend URL that should ever appear in
 * frontend code — it's public by design (points at our own API), unlike
 * ANTHROPIC_API_KEY / OPENAI_API_KEY / S3 credentials, which must never be
 * referenced from any file under app/ or components/.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "Request failed");
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions extends RequestInit {
  organizationId?: string;
  accessToken?: string;
}

async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { organizationId, accessToken, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string> | undefined),
  };

  if (accessToken) {
    finalHeaders.Authorization = `Bearer ${accessToken}`;
  }
  if (organizationId) {
    finalHeaders["X-Organization-Id"] = organizationId;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await response.json() : undefined;

  if (!response.ok) {
    throw new ApiError(response.status, body?.detail ?? body);
  }

  return body as T;
}

// ---- Types mirroring backend Pydantic schemas -----------------------------

export interface UserPublic {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  phone: string | null;
  timezone: string | null;
  is_active: boolean;
  is_email_verified: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface MessageResponse {
  message: string;
}

export interface OrganizationPublic {
  id: string;
  name: string;
  slug: string;
  plan_type: string;
  is_agency: boolean;
}

export type MarketingGoal = "sales" | "leads" | "website_traffic" | "brand_awareness";

export interface BusinessProfilePublic {
  id: string;
  organization_id: string;
  website_url: string | null;
  industry: string | null;
  country: string | null;
  products_services: string | null;
  target_customers: string | null;
  marketing_goal: MarketingGoal | null;
  monthly_ad_budget: number | null;
  budget_currency: string;
  social_platforms: string[] | null;
  advertising_platforms: string[] | null;
  onboarding_completed_at: string | null;
  onboarding_current_step: number;
}

export interface RolePublic {
  id: string;
  name: string;
  description: string | null;
}

export interface OrganizationMemberPublic {
  id: string;
  user_id: string;
  email: string;
  full_name: string | null;
  role: RolePublic;
}

export interface DashboardSummary {
  business_name: string;
  marketing_goal: MarketingGoal | null;
  monthly_ad_budget: number | null;
  budget_currency: string;
  connected_platforms_count: number;
  onboarding_completed: boolean;
  campaign_count: number;
  content_count: number;
  leads_count: number;
  sales_count: number;
  total_spend: number;
  spend_currency: string;
}

// ---- Auth -------------------------------------------------------------

export function registerAccount(data: {
  email: string;
  password: string;
  full_name: string;
  organization_name: string;
}) {
  return apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function login(data: { email: string; password: string }) {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function logout(refreshToken: string) {
  return apiFetch<MessageResponse>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export function getCurrentUser(accessToken: string) {
  return apiFetch<UserPublic>("/auth/me", { accessToken });
}

export function forgotPassword(email: string) {
  return apiFetch<MessageResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, newPassword: string) {
  return apiFetch<MessageResponse>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export function verifyEmail(token: string) {
  return apiFetch<MessageResponse>("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function resendVerification(email: string) {
  return apiFetch<MessageResponse>("/auth/resend-verification", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

// ---- User profile ------------------------------------------------------

export function updateMyProfile(
  accessToken: string,
  data: Partial<{ full_name: string; phone: string; timezone: string; avatar_url: string }>
) {
  return apiFetch<UserPublic>("/users/me", {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(data),
  });
}

export function changeMyPassword(
  accessToken: string,
  data: { current_password: string; new_password: string }
) {
  return apiFetch<MessageResponse>("/users/me/change-password", {
    method: "POST",
    accessToken,
    body: JSON.stringify(data),
  });
}

// ---- Organizations ------------------------------------------------------

export function listOrganizations(accessToken: string) {
  return apiFetch<OrganizationPublic[]>("/organizations", { accessToken });
}

export function createOrganization(
  accessToken: string,
  data: { name: string; is_agency?: boolean }
) {
  return apiFetch<OrganizationPublic>("/organizations", {
    method: "POST",
    accessToken,
    body: JSON.stringify(data),
  });
}

export function getCurrentOrganization(accessToken: string, organizationId: string) {
  return apiFetch<OrganizationPublic>("/organizations/current", { accessToken, organizationId });
}

export function updateCurrentOrganization(
  accessToken: string,
  organizationId: string,
  data: { name?: string }
) {
  return apiFetch<OrganizationPublic>("/organizations/current", {
    method: "PATCH",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

// ---- Onboarding ---------------------------------------------------------

export function getOnboardingState(accessToken: string, organizationId: string) {
  return apiFetch<BusinessProfilePublic>("/onboarding", { accessToken, organizationId });
}

function saveOnboardingStep(
  accessToken: string,
  organizationId: string,
  step: string,
  data: Record<string, unknown>
) {
  return apiFetch<BusinessProfilePublic>(`/onboarding/${step}`, {
    method: "PUT",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

export const onboarding = {
  saveWebsite: (accessToken: string, organizationId: string, website_url: string | null) =>
    saveOnboardingStep(accessToken, organizationId, "step-2-website", { website_url }),
  saveIndustry: (accessToken: string, organizationId: string, industry: string) =>
    saveOnboardingStep(accessToken, organizationId, "step-3-industry", { industry }),
  saveCountry: (accessToken: string, organizationId: string, country: string) =>
    saveOnboardingStep(accessToken, organizationId, "step-4-country", { country }),
  saveProductsServices: (accessToken: string, organizationId: string, products_services: string) =>
    saveOnboardingStep(accessToken, organizationId, "step-5-products-services", { products_services }),
  saveTargetCustomers: (accessToken: string, organizationId: string, target_customers: string) =>
    saveOnboardingStep(accessToken, organizationId, "step-6-target-customers", { target_customers }),
  saveMarketingGoal: (accessToken: string, organizationId: string, marketing_goal: MarketingGoal) =>
    saveOnboardingStep(accessToken, organizationId, "step-7-marketing-goal", { marketing_goal }),
  saveBudget: (
    accessToken: string,
    organizationId: string,
    monthly_ad_budget: number,
    budget_currency: string = "USD"
  ) =>
    saveOnboardingStep(accessToken, organizationId, "step-8-budget", {
      monthly_ad_budget,
      budget_currency,
    }),
  saveSocialPlatforms: (accessToken: string, organizationId: string, social_platforms: string[]) =>
    saveOnboardingStep(accessToken, organizationId, "step-9-social-platforms", { social_platforms }),
  saveAdvertisingPlatforms: (
    accessToken: string,
    organizationId: string,
    advertising_platforms: string[]
  ) =>
    saveOnboardingStep(accessToken, organizationId, "step-10-advertising-platforms", {
      advertising_platforms,
    }),
  complete: (accessToken: string, organizationId: string) =>
    apiFetch<BusinessProfilePublic>("/onboarding/complete", {
      method: "POST",
      accessToken,
      organizationId,
    }),
};

// ---- Team members & roles ------------------------------------------------

export function listRoles(accessToken: string, organizationId: string) {
  return apiFetch<RolePublic[]>("/roles", { accessToken, organizationId });
}

export function listMembers(accessToken: string, organizationId: string) {
  return apiFetch<OrganizationMemberPublic[]>("/organizations/current/members", {
    accessToken,
    organizationId,
  });
}

export function inviteMember(
  accessToken: string,
  organizationId: string,
  data: { email: string; role_name: string }
) {
  return apiFetch<OrganizationMemberPublic>("/organizations/current/members", {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

export function updateMemberRole(
  accessToken: string,
  organizationId: string,
  memberId: string,
  roleName: string
) {
  return apiFetch<OrganizationMemberPublic>(`/organizations/current/members/${memberId}`, {
    method: "PATCH",
    accessToken,
    organizationId,
    body: JSON.stringify({ role_name: roleName }),
  });
}

export function removeMember(accessToken: string, organizationId: string, memberId: string) {
  return apiFetch<MessageResponse>(`/organizations/current/members/${memberId}`, {
    method: "DELETE",
    accessToken,
    organizationId,
  });
}

// ---- Dashboard ------------------------------------------------------------

export function getDashboardSummary(accessToken: string, organizationId: string) {
  return apiFetch<DashboardSummary>("/dashboard/summary", { accessToken, organizationId });
}

// ---- AI Agents (Week 3) ----------------------------------------------------

export interface AgentInfo {
  name: string;
  description: string;
}

export interface RunAgentResponse {
  agent: string;
  success: boolean;
  output: string | null;
  requires_human_approval: boolean;
  notes: string | null;
}

export function listAgents(accessToken: string, organizationId: string) {
  return apiFetch<AgentInfo[]>("/agents", { accessToken, organizationId });
}

export function runAgent(
  accessToken: string,
  organizationId: string,
  agentName: string,
  brief?: string
) {
  return apiFetch<RunAgentResponse>(`/agents/${agentName}/run`, {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify({ brief: brief ?? null }),
  });
}

// ---- AI Chat (Week 3) -------------------------------------------------------

export interface ChatMessagePublic {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationPublic {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationPublic {
  messages: ChatMessagePublic[];
}

export interface SendMessageResponse {
  conversation_id: string;
  message: ChatMessagePublic;
}

export function listConversations(accessToken: string, organizationId: string) {
  return apiFetch<ConversationPublic[]>("/chat/conversations", { accessToken, organizationId });
}

export function getConversation(accessToken: string, organizationId: string, conversationId: string) {
  return apiFetch<ConversationDetail>(`/chat/conversations/${conversationId}`, {
    accessToken,
    organizationId,
  });
}

export function sendChatMessage(
  accessToken: string,
  organizationId: string,
  data: { message: string; conversation_id?: string | null }
) {
  return apiFetch<SendMessageResponse>("/chat/messages", {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

// ---- AI Usage tracking (Week 3) --------------------------------------------

export interface AIUsageSummary {
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_estimated_cost_usd: number | null;
  by_source: Record<string, number>;
}

export function getAIUsageSummary(accessToken: string, organizationId: string) {
  return apiFetch<AIUsageSummary>("/ai-usage/summary", { accessToken, organizationId });
}

// ---- Campaign Builder (Week 4) ---------------------------------------------

export type CampaignStatus = "draft" | "generating" | "generated" | "approved";

export interface CampaignPublic {
  id: string;
  status: CampaignStatus;
  product_name: string;
  product_price: number | null;
  product_description: string | null;
  objective: MarketingGoal;
  desired_outcome_count: number | null;
  target_location: string | null;
  target_audience: string | null;
  existing_customer_info: string | null;
  budget_amount: number | null;
  budget_currency: string;
  duration_days: number | null;
  landing_page_url: string | null;
  generated_at: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdCopyVariantPublic {
  id: string;
  variant_number: number;
  headline: string;
  primary_text: string;
  description: string | null;
  call_to_action: string;
  is_edited: boolean;
}

export type CreativeConceptType = "image" | "video" | "hook" | "visual_direction" | "ugc";

export interface CreativeConceptPublic {
  id: string;
  concept_type: CreativeConceptType;
  title: string;
  description: string;
}

export interface CampaignStrategyPublic {
  strategy: {
    objective?: string;
    funnel_stage?: string;
    target_customer?: string;
    pain_points?: string[];
    value_proposition?: string;
    offer?: string;
    cta?: string;
  };
  audience: {
    demographics?: string;
    geography?: string;
    interests?: string[];
    behaviors?: string[];
    lookalike_strategy?: string;
    retargeting_strategy?: string;
  };
  budget_strategy: {
    test_budget?: string;
    ad_set_count?: number;
    budget_allocation?: string;
    testing_period_days?: number;
    scaling_rules?: string;
  };
}

export interface CampaignDetail extends CampaignPublic {
  strategy: CampaignStrategyPublic | null;
  ad_copy_variants: AdCopyVariantPublic[];
  creative_concepts: CreativeConceptPublic[];
}

export interface CampaignCreateInput {
  product_name: string;
  product_price?: number | null;
  product_description?: string | null;
  objective: MarketingGoal;
  desired_outcome_count?: number | null;
  target_location?: string | null;
  target_audience?: string | null;
  existing_customer_info?: string | null;
  budget_amount?: number | null;
  budget_currency?: string;
  duration_days?: number | null;
  landing_page_url?: string | null;
}

export function listCampaigns(accessToken: string, organizationId: string) {
  return apiFetch<CampaignPublic[]>("/campaigns", { accessToken, organizationId });
}

export function createCampaign(
  accessToken: string,
  organizationId: string,
  data: CampaignCreateInput
) {
  return apiFetch<CampaignPublic>("/campaigns", {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

export function getCampaign(accessToken: string, organizationId: string, campaignId: string) {
  return apiFetch<CampaignDetail>(`/campaigns/${campaignId}`, { accessToken, organizationId });
}

export function updateCampaign(
  accessToken: string,
  organizationId: string,
  campaignId: string,
  data: Partial<CampaignCreateInput>
) {
  return apiFetch<CampaignPublic>(`/campaigns/${campaignId}`, {
    method: "PATCH",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

export function deleteCampaign(accessToken: string, organizationId: string, campaignId: string) {
  return apiFetch<MessageResponse>(`/campaigns/${campaignId}`, {
    method: "DELETE",
    accessToken,
    organizationId,
  });
}

export function generateCampaign(accessToken: string, organizationId: string, campaignId: string) {
  return apiFetch<CampaignDetail>(`/campaigns/${campaignId}/generate`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

export function approveCampaign(accessToken: string, organizationId: string, campaignId: string) {
  return apiFetch<CampaignPublic>(`/campaigns/${campaignId}/approve`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

export function updateAdCopyVariant(
  accessToken: string,
  organizationId: string,
  campaignId: string,
  variantId: string,
  data: Partial<Pick<AdCopyVariantPublic, "headline" | "primary_text" | "description" | "call_to_action">>
) {
  return apiFetch<AdCopyVariantPublic>(`/campaigns/${campaignId}/ad-copy-variants/${variantId}`, {
    method: "PATCH",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

// ---- Experiments (Week 4) ---------------------------------------------------

export type ExperimentDimension = "audience" | "headline" | "hook" | "creative";

export interface ExperimentPublic {
  id: string;
  name: string;
  dimension: ExperimentDimension;
  description: string | null;
  variant_ids: string[];
  created_at: string;
}

export function listExperiments(accessToken: string, organizationId: string, campaignId: string) {
  return apiFetch<ExperimentPublic[]>(`/campaigns/${campaignId}/experiments`, {
    accessToken,
    organizationId,
  });
}

export function createExperiment(
  accessToken: string,
  organizationId: string,
  campaignId: string,
  data: { name: string; dimension: ExperimentDimension; description?: string | null; variant_ids: string[] }
) {
  return apiFetch<ExperimentPublic>(`/campaigns/${campaignId}/experiments`, {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

// ---- Brand voice (Week 5) ---------------------------------------------------

export type BrandVoice =
  | "professional"
  | "friendly"
  | "luxury"
  | "educational"
  | "funny"
  | "bold"
  | "inspirational"
  | "custom";

export const BRAND_VOICE_OPTIONS: { value: BrandVoice; label: string }[] = [
  { value: "professional", label: "Professional" },
  { value: "friendly", label: "Friendly" },
  { value: "luxury", label: "Luxury" },
  { value: "educational", label: "Educational" },
  { value: "funny", label: "Funny" },
  { value: "bold", label: "Bold" },
  { value: "inspirational", label: "Inspirational" },
  { value: "custom", label: "Custom" },
];

export interface BrandVoiceProfile {
  brand_voice: BrandVoice | null;
  brand_voice_custom: string | null;
}

export function getBrandVoice(accessToken: string, organizationId: string) {
  return apiFetch<BrandVoiceProfile>("/business-profile/brand-voice", { accessToken, organizationId });
}

export function setBrandVoice(
  accessToken: string,
  organizationId: string,
  data: { brand_voice: BrandVoice; brand_voice_custom?: string | null }
) {
  return apiFetch<BrandVoiceProfile>("/business-profile/brand-voice", {
    method: "PUT",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

// ---- Content assets (Week 5) -------------------------------------------------

export type AssetType = "image" | "video";
export type AssetStatus = "uploaded" | "analyzing" | "analyzed" | "failed";

export interface ContentAssetPublic {
  id: string;
  asset_type: AssetType;
  status: AssetStatus;
  original_filename: string;
  content_type: string;
  size_bytes: number | null;
  ai_description: string | null;
  analysis_error: string | null;
  created_at: string;
}

export interface ContentAssetWithUrl extends ContentAssetPublic {
  url: string | null;
}

export async function uploadContentAsset(
  accessToken: string,
  organizationId: string,
  file: File
): Promise<ContentAssetWithUrl> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/content-assets`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "X-Organization-Id": organizationId,
      // No Content-Type set deliberately — the browser sets
      // multipart/form-data with the correct boundary itself. Setting it
      // manually (as apiFetch's JSON default does) would corrupt the
      // upload, so this bypasses apiFetch entirely rather than adding an
      // escape hatch to it for one caller.
    },
    body: formData,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await response.json() : undefined;
  if (!response.ok) {
    throw new ApiError(response.status, body?.detail ?? body);
  }
  return body as ContentAssetWithUrl;
}

export function listContentAssets(accessToken: string, organizationId: string) {
  return apiFetch<ContentAssetPublic[]>("/content-assets", { accessToken, organizationId });
}

export function getContentAsset(accessToken: string, organizationId: string, assetId: string) {
  return apiFetch<ContentAssetWithUrl>(`/content-assets/${assetId}`, { accessToken, organizationId });
}

export function deleteContentAsset(accessToken: string, organizationId: string, assetId: string) {
  return apiFetch<MessageResponse>(`/content-assets/${assetId}`, {
    method: "DELETE",
    accessToken,
    organizationId,
  });
}

// ---- Content (Week 5) --------------------------------------------------------

export type ContentType =
  | "facebook_post"
  | "instagram_caption"
  | "linkedin_post"
  | "x_post"
  | "tiktok_caption"
  | "youtube_title"
  | "youtube_description"
  | "blog_post"
  | "product_description"
  | "email"
  | "video_script"
  | "hook";

export const CONTENT_TYPE_OPTIONS: { value: ContentType; label: string }[] = [
  { value: "facebook_post", label: "Facebook post" },
  { value: "instagram_caption", label: "Instagram caption" },
  { value: "linkedin_post", label: "LinkedIn post" },
  { value: "x_post", label: "X post" },
  { value: "tiktok_caption", label: "TikTok caption" },
  { value: "youtube_title", label: "YouTube title" },
  { value: "youtube_description", label: "YouTube description" },
  { value: "blog_post", label: "Blog post" },
  { value: "product_description", label: "Product description" },
  { value: "email", label: "Email" },
];

export type ContentStatus = "draft" | "approved";

export interface ContentPublic {
  id: string;
  content_type: ContentType;
  status: ContentStatus;
  title: string | null;
  body: string;
  source_text: string | null;
  source_url: string | null;
  source_asset_id: string | null;
  brand_voice_used: BrandVoice | null;
  repurpose_batch_id: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GenerateContentInput {
  content_type: ContentType;
  source_text?: string | null;
  source_url?: string | null;
  source_asset_id?: string | null;
}

export function generateContent(accessToken: string, organizationId: string, data: GenerateContentInput) {
  return apiFetch<ContentPublic>("/content/generate", {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

export function listContent(
  accessToken: string,
  organizationId: string,
  filters?: { status?: ContentStatus; content_type?: ContentType; search?: string }
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.content_type) params.set("content_type", filters.content_type);
  if (filters?.search) params.set("search", filters.search);
  const query = params.toString();
  return apiFetch<ContentPublic[]>(`/content${query ? `?${query}` : ""}`, { accessToken, organizationId });
}

export function getContent(accessToken: string, organizationId: string, contentId: string) {
  return apiFetch<ContentPublic>(`/content/${contentId}`, { accessToken, organizationId });
}

export function updateContent(
  accessToken: string,
  organizationId: string,
  contentId: string,
  data: { title?: string | null; body?: string }
) {
  return apiFetch<ContentPublic>(`/content/${contentId}`, {
    method: "PATCH",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

export function approveContent(accessToken: string, organizationId: string, contentId: string) {
  return apiFetch<ContentPublic>(`/content/${contentId}/approve`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

export function deleteContentItem(accessToken: string, organizationId: string, contentId: string) {
  return apiFetch<MessageResponse>(`/content/${contentId}`, {
    method: "DELETE",
    accessToken,
    organizationId,
  });
}

// ---- Content repurposing (Week 5) --------------------------------------------

export interface RepurposeBatchPublic {
  id: string;
  source_text: string | null;
  source_url: string | null;
  source_asset_id: string | null;
  created_at: string;
  items: ContentPublic[];
}

export function repurposeContent(
  accessToken: string,
  organizationId: string,
  data: { source_text?: string | null; source_url?: string | null; source_asset_id?: string | null }
) {
  return apiFetch<RepurposeBatchPublic>("/content/repurpose", {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

export function getRepurposeBatch(accessToken: string, organizationId: string, batchId: string) {
  return apiFetch<RepurposeBatchPublic>(`/content/repurpose-batches/${batchId}`, {
    accessToken,
    organizationId,
  });
}

// ---- SEO (Week 5) -------------------------------------------------------------

export interface SEOContentPublic {
  id: string;
  content_id: string | null;
  topic: string;
  primary_keyword: string | null;
  secondary_keywords: string[] | null;
  search_intent: string | null;
  seo_title: string | null;
  meta_description: string | null;
  url_slug: string | null;
  h1: string | null;
  h2_structure: string[] | null;
  internal_linking_suggestions: string[] | null;
  image_alt_text: string | null;
  hashtags: string[] | null;
  created_at: string;
  updated_at: string;
}

export function generateSEO(
  accessToken: string,
  organizationId: string,
  data: { topic: string; content_id?: string | null }
) {
  return apiFetch<SEOContentPublic>("/seo/generate", {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

// ---- Projects (Week 6) -------------------------------------------------------

export interface ProjectPublic {
  id: string;
  name: string;
  website_url: string | null;
  description: string | null;
  industry: string | null;
  created_at: string;
  updated_at: string;
}

export function listProjects(accessToken: string, organizationId: string) {
  return apiFetch<ProjectPublic[]>("/projects", { accessToken, organizationId });
}

export function createProject(
  accessToken: string,
  organizationId: string,
  data: { name: string; website_url?: string | null; description?: string | null; industry?: string | null }
) {
  return apiFetch<ProjectPublic>("/projects", {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

// ---- Connected accounts / OAuth (Week 6) ------------------------------------

export type SocialPlatform =
  | "facebook_page"
  | "instagram_business"
  | "linkedin_page"
  | "x_account"
  | "tiktok_account"
  | "youtube_channel";

export const SOCIAL_PLATFORM_LABELS: Record<SocialPlatform, string> = {
  facebook_page: "Facebook",
  instagram_business: "Instagram",
  linkedin_page: "LinkedIn",
  x_account: "X",
  tiktok_account: "TikTok",
  youtube_channel: "YouTube",
};

export type ConnectionStatus = "connected" | "disconnected" | "expired" | "error";

export interface ConnectedAccountPublic {
  id: string;
  project_id: string;
  platform: SocialPlatform;
  status: ConnectionStatus;
  external_account_id: string | null;
  external_account_name: string | null;
  granted_scopes: string | null;
  token_expires_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface SupportedPlatform {
  platform: SocialPlatform;
  display_name: string;
  configured: boolean;
}

export function listSupportedPlatforms(accessToken: string, organizationId: string) {
  // No auth actually required server-side, but accessToken/organizationId
  // are accepted here for a consistent call signature with every other
  // function in this file.
  return apiFetch<SupportedPlatform[]>("/oauth/platforms", { accessToken, organizationId });
}

export function startConnectFlow(
  accessToken: string,
  organizationId: string,
  platform: SocialPlatform,
  projectId: string
) {
  return apiFetch<{ authorize_url: string }>(`/oauth/${platform}/connect`, {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify({ project_id: projectId }),
  });
}

export function listConnectedAccounts(accessToken: string, organizationId: string) {
  return apiFetch<ConnectedAccountPublic[]>("/connected-accounts", { accessToken, organizationId });
}

export function disconnectAccount(accessToken: string, organizationId: string, accountId: string) {
  return apiFetch<ConnectedAccountPublic>(`/connected-accounts/${accountId}/disconnect`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

export function reauthorizeAccount(accessToken: string, organizationId: string, accountId: string) {
  return apiFetch<{ authorize_url: string }>(`/connected-accounts/${accountId}/reauthorize`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

// ---- Scheduled posts / calendar (Week 6) -------------------------------------

export type ScheduledPostStatus = "draft" | "scheduled" | "publishing" | "published" | "failed";

export interface ScheduledPostPublic {
  id: string;
  content_id: string;
  connected_account_id: string;
  status: ScheduledPostStatus;
  scheduled_for: string | null;
  published_at: string | null;
  external_post_id: string | null;
  external_post_url: string | null;
  retry_count: number;
  ai_recommended_post_time: string | null;
  ai_recommended_platform: string | null;
  ai_recommended_format: string | null;
  ai_recommended_hashtags: string[] | null;
  ai_recommendation_rationale: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublishingLogPublic {
  id: string;
  outcome: "success" | "failure";
  request_summary: string;
  error_message: string | null;
  attempt_number: number;
  created_at: string;
}

export interface ScheduledPostDetail extends ScheduledPostPublic {
  publishing_logs: PublishingLogPublic[];
}

export function listScheduledPosts(
  accessToken: string,
  organizationId: string,
  filters?: { status?: ScheduledPostStatus; start?: string; end?: string }
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.start) params.set("start", filters.start);
  if (filters?.end) params.set("end", filters.end);
  const query = params.toString();
  return apiFetch<ScheduledPostPublic[]>(`/scheduled-posts${query ? `?${query}` : ""}`, {
    accessToken,
    organizationId,
  });
}

export function getScheduledPost(accessToken: string, organizationId: string, postId: string) {
  return apiFetch<ScheduledPostDetail>(`/scheduled-posts/${postId}`, { accessToken, organizationId });
}

export function createDraftPost(
  accessToken: string,
  organizationId: string,
  data: { content_id: string; connected_account_id: string }
) {
  return apiFetch<ScheduledPostPublic>("/scheduled-posts", {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify(data),
  });
}

export function schedulePost(
  accessToken: string,
  organizationId: string,
  postId: string,
  scheduledFor: string
) {
  return apiFetch<ScheduledPostPublic>(`/scheduled-posts/${postId}/schedule`, {
    method: "POST",
    accessToken,
    organizationId,
    body: JSON.stringify({ scheduled_for: scheduledFor }),
  });
}

export function publishNow(accessToken: string, organizationId: string, postId: string) {
  return apiFetch<ScheduledPostPublic>(`/scheduled-posts/${postId}/publish-now`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

export function retryFailedPost(accessToken: string, organizationId: string, postId: string) {
  return apiFetch<ScheduledPostPublic>(`/scheduled-posts/${postId}/retry`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

export function cancelScheduledPost(accessToken: string, organizationId: string, postId: string) {
  return apiFetch<ScheduledPostPublic>(`/scheduled-posts/${postId}/cancel`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

export function deleteScheduledPost(accessToken: string, organizationId: string, postId: string) {
  return apiFetch<MessageResponse>(`/scheduled-posts/${postId}`, {
    method: "DELETE",
    accessToken,
    organizationId,
  });
}

export function recommendPosting(accessToken: string, organizationId: string, postId: string) {
  return apiFetch<ScheduledPostPublic>(`/scheduled-posts/${postId}/recommend`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}

export function acceptRecommendation(accessToken: string, organizationId: string, postId: string) {
  return apiFetch<ScheduledPostPublic>(`/scheduled-posts/${postId}/accept-recommendation`, {
    method: "POST",
    accessToken,
    organizationId,
  });
}
