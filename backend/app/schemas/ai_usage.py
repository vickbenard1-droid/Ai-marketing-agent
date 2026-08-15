from pydantic import BaseModel


class AIUsageSummary(BaseModel):
    total_calls: int
    successful_calls: int
    failed_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: float | None
    by_source: dict[str, int]
