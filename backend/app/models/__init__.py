"""
Import every model here so that:
1. Alembic's autogenerate can discover all tables via Base.metadata.
2. Relationship string references (e.g. "OrganizationMember") resolve correctly.
"""
from app.models.user import User                          # noqa: F401
from app.models.organization import (                     # noqa: F401
    Organization,
    Role,
    OrganizationMember,
)
from app.models.project import Project                    # noqa: F401
from app.models.connected_account import (                # noqa: F401
    ConnectedAccount,
    PlatformType,
    ConnectionStatus,
    ORGANIC_SOCIAL_PLATFORMS,
)
from app.models.audit_log import AuditLog                  # noqa: F401
from app.models.email_token import EmailToken, EmailTokenType   # noqa: F401
from app.models.business_profile import BusinessProfile, MarketingGoal, BrandVoice  # noqa: F401
from app.models.revoked_token import RevokedToken  # noqa: F401
from app.models.ai_usage_log import AIUsageLog, AIUsageSource  # noqa: F401
from app.models.approval_request import ApprovalRequest, ApprovalStatus, ApprovalActionType  # noqa: F401
from app.models.conversation import Conversation, ChatMessage, ChatRole  # noqa: F401
from app.models.campaign import Campaign, CampaignStatus, MarketingObjective  # noqa: F401
from app.models.campaign_strategy import CampaignStrategy  # noqa: F401
from app.models.ad_copy_variant import AdCopyVariant  # noqa: F401
from app.models.creative_concept import CreativeConcept, CreativeConceptType  # noqa: F401
from app.models.experiment import Experiment, ExperimentDimension  # noqa: F401
from app.models.content_asset import ContentAsset, AssetType, AssetStatus  # noqa: F401
from app.models.content_repurpose_batch import ContentRepurposeBatch  # noqa: F401
from app.models.content import Content, ContentType, ContentStatus  # noqa: F401
from app.models.seo_content import SEOContent  # noqa: F401
from app.models.oauth_state import OAuthState  # noqa: F401
from app.models.scheduled_post import ScheduledPost, ScheduledPostStatus  # noqa: F401
from app.models.publishing_log import PublishingLog, PublishingLogOutcome  # noqa: F401
from app.models.meta_ad_account import MetaAdAccount  # noqa: F401
from app.models.ad_account_spend_limit import AdAccountSpendLimit  # noqa: F401
from app.models.meta_campaign import MetaCampaign, MetaCampaignObjective, MetaCampaignStatus  # noqa: F401
from app.models.meta_campaign_spend_limit import MetaCampaignSpendLimit  # noqa: F401
from app.models.meta_ad_set import MetaAdSet, MetaAdSetStatus  # noqa: F401
from app.models.meta_ad import MetaAd, MetaAdStatus  # noqa: F401
from app.models.meta_insight_snapshot import MetaInsightSnapshot, MetaInsightEntityType  # noqa: F401
