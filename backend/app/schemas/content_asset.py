import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.content_asset import AssetStatus, AssetType


class ContentAssetPublic(BaseModel):
    id: uuid.UUID
    asset_type: AssetType
    status: AssetStatus
    original_filename: str
    content_type: str
    size_bytes: int | None
    ai_description: str | None
    analysis_error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentAssetWithUrl(ContentAssetPublic):
    """
    Adds the presigned read URL - kept separate from ContentAssetPublic
    since generating it is an extra call (see
    app/storage/client.py::get_presigned_url) that only the detail/list
    views need, not every internal reference to an asset.
    """

    url: str | None
