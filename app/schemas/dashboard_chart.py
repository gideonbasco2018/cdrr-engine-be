# app/schemas/dashboard_chart.py

from pydantic import BaseModel, Field, computed_field
from typing import Optional, List
from datetime import date


# ─────────────────────────────────────────────────────────
# Single data point (one row in the chart / table)
# ─────────────────────────────────────────────────────────
class ChartDataPoint(BaseModel):
    """One time bucket: day, month, or year."""

    label:      str = Field(..., description="Display label  e.g. '1', 'Jan', '2026'")
    received:   int = Field(..., description="Total applications received in this bucket")
    completed:  int = Field(..., description="Completed applications in this bucket")
    on_process: int = Field(..., description="In-flight applications in this bucket")

    @computed_field
    @property
    def completed_rate(self) -> Optional[float]:
        """Completion % rounded to 1 decimal. None when received = 0."""
        if self.received == 0:
            return None
        return round((self.completed / self.received) * 100, 1)

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────
# Full chart response
# ─────────────────────────────────────────────────────────
class ChartResponse(BaseModel):
    """
    Payload returned by /chart  (daily / monthly / yearly).

    Frontend receives:
    - breakdown  →  which mode was used
    - data       →  ordered list of ChartDataPoint
    - totals     →  aggregate across all buckets in the response
    """

    username:   str                  = Field(..., description="Effective username")
    breakdown:  str                  = Field(..., description="'day' | 'month' | 'year'")
    date_from:  Optional[date]       = None
    date_to:    Optional[date]       = None
    data:       List[ChartDataPoint] = Field(default_factory=list)

    # ── Aggregate totals (pre-computed server-side) ───────────────────
    total_received:   int            = Field(..., description="Sum of received across all buckets")
    total_completed:  int            = Field(..., description="Sum of completed across all buckets")
    total_on_process: int            = Field(..., description="Sum of on_process across all buckets")

    @computed_field
    @property
    def overall_completed_rate(self) -> Optional[float]:
        if self.total_received == 0:
            return None
        return round((self.total_completed / self.total_received) * 100, 1)

    class Config:
        from_attributes = True