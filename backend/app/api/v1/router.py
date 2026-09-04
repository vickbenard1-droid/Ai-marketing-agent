from fastapi import APIRouter

from app.api.v1.endpoints import (
    agents,
    ai_usage,
    analytics,
    auth,
    business_profile,
    campaign_generation,
    campaigns,
    chat,
    connected_accounts,
    content,
    content_assets,
    content_generation,
    dashboard,
    experiments,
    leads,
    members,
    meta_ads,
    onboarding,
    optimization,
    tracking,
    organizations,
    projects,
    scheduled_posts,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
api_router.include_router(onboarding.router)
api_router.include_router(business_profile.router)
api_router.include_router(members.router)
api_router.include_router(members.roles_router)
api_router.include_router(dashboard.router)
api_router.include_router(agents.router)
api_router.include_router(chat.router)
api_router.include_router(ai_usage.router)
api_router.include_router(campaigns.router)
api_router.include_router(campaign_generation.router)
api_router.include_router(experiments.router)
api_router.include_router(content.router)
api_router.include_router(content_generation.router)
api_router.include_router(content_assets.router)
api_router.include_router(projects.router)
api_router.include_router(connected_accounts.router)
api_router.include_router(scheduled_posts.router)
api_router.include_router(meta_ads.router)
api_router.include_router(analytics.router)
api_router.include_router(tracking.router)
api_router.include_router(optimization.router)
api_router.include_router(leads.router)
