import uuid
from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel, Field

from app.models.conversion_type import ConversionCategory


class TrackPageViewRequest(BaseModel):
    tracking_key: str
    visitor_id: str
    page_url: Optional[str] = None
    utm_json: dict = Field(default_factory=dict)


class TrackConversionRequest(BaseModel):
    tracking_key: str
    visitor_id: str
    conversion_type_name: str
    conversion_value_cents: Optional[int] = None
    page_url: Optional[str] = None
    utm_json: dict = Field(default_factory=dict)


class TrackingKeyPublic(BaseModel):
    key: str

    model_config = {"from_attributes": True}


class RawTotalsPublic(BaseModel):
    impressions: int
    clicks: int
    spend_cents: int
    leads_count: Optional[int]
    purchases_count: Optional[int]
    revenue_cents: Optional[int]
    reach: Optional[int]


class DerivedMetricsPublic(BaseModel):
    ctr: Optional[float]
    cpc_cents: Optional[float]
    cpm_cents: Optional[float]
    cost_per_lead_cents: Optional[float]
    cpa_cents: Optional[float]
    roas: Optional[float]
    conversion_rate: Optional[float]


class DashboardResponse(BaseModel):
    raw: RawTotalsPublic
    derived: DerivedMetricsPublic


class ConversionTypePublic(BaseModel):
    id: uuid.UUID
    name: str
    category: ConversionCategory
    description: Optional[str]
    counts_as_revenue: bool
    is_active: bool

    model_config = {"from_attributes": True}


class CreateConversionTypeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: ConversionCategory
    description: Optional[str] = Field(default=None, max_length=1000)
    counts_as_revenue: bool = False
