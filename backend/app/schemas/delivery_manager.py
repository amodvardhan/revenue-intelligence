"""Delivery manager (directory user) ↔ customer assignment APIs."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class TenantUserItem(BaseModel):
    user_id: UUID
    email: str


class CustomerRef(BaseModel):
    customer_id: UUID
    customer_name: str


class DeliveryManagerAssignmentRow(BaseModel):
    assignment_id: UUID
    org_id: UUID
    customer_id: UUID
    customer_legal: str
    delivery_manager_user_id: UUID
    delivery_manager_email: str
    valid_from: date


class DeliveryManagerAssignmentListResponse(BaseModel):
    items: list[DeliveryManagerAssignmentRow]


class CustomerListResponse(BaseModel):
    items: list[CustomerRef]


class TenantUserListResponse(BaseModel):
    items: list[TenantUserItem]


class AssignDeliveryManagerBody(BaseModel):
    org_id: UUID = Field(description="Organization that scopes the customer")
    customer_id: UUID
    delivery_manager_user_id: UUID = Field(description="Directory user who owns the customer relationship")
