"""Task type definitions and field specs for the Tripletex AI Accounting Agent."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """All known task types across Tier 1–3."""

    # Tier 1 — Foundational (×1 multiplier)
    CREATE_EMPLOYEE = "create_employee"
    UPDATE_EMPLOYEE = "update_employee"
    DELETE_EMPLOYEE = "delete_employee"
    SET_EMPLOYEE_ROLES = "set_employee_roles"
    CREATE_CUSTOMER = "create_customer"
    UPDATE_CUSTOMER = "update_customer"
    CREATE_PRODUCT = "create_product"
    DELETE_PRODUCT = "delete_product"
    UPDATE_PRODUCT = "update_product"
    CREATE_INVOICE = "create_invoice"
    CREATE_DEPARTMENT = "create_department"
    CREATE_PROJECT = "create_project"

    # Tier 2 — Multi-step workflows (×2 multiplier)
    INVOICE_EXISTING_CUSTOMER = "invoice_existing_customer"
    REGISTER_PAYMENT = "register_payment"
    CREATE_CREDIT_NOTE = "create_credit_note"
    INVOICE_WITH_PAYMENT = "invoice_with_payment"
    CREATE_TRAVEL_EXPENSE = "create_travel_expense"
    DELETE_TRAVEL_EXPENSE = "delete_travel_expense"
    PROJECT_WITH_CUSTOMER = "project_with_customer"
    PROJECT_BILLING = "project_billing"
    CREATE_CONTACT = "create_contact"
    FIND_CUSTOMER = "find_customer"
    UPDATE_PROJECT = "update_project"
    DELETE_PROJECT = "delete_project"
    LOG_HOURS = "log_hours"
    DELETE_CUSTOMER = "delete_customer"
    UPDATE_CONTACT = "update_contact"
    UPDATE_DEPARTMENT = "update_department"
    CREATE_SUPPLIER_INVOICE = "create_supplier_invoice"
    CREATE_SUPPLIER = "create_supplier"
    DELETE_DEPARTMENT = "delete_department"
    DELETE_SUPPLIER = "delete_supplier"
    FIND_SUPPLIER = "find_supplier"
    UPDATE_SUPPLIER = "update_supplier"
    RUN_PAYROLL = "run_payroll"
    REVERSE_PAYMENT = "reverse_payment"

    # Tier 3 — Complex scenarios (×3 multiplier)
    BANK_RECONCILIATION = "bank_reconciliation"
    ERROR_CORRECTION = "error_correction"
    YEAR_END_CLOSING = "year_end_closing"
    ENABLE_MODULE = "enable_module"
    CREATE_DIMENSION_VOUCHER = "create_dimension_voucher"

    # Fallback
    UNKNOWN = "unknown"


class TaskClassification(BaseModel):
    """Result of classifying a natural-language task prompt."""

    task_type: TaskType
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence 0–1")
    fields: dict[str, Any] = Field(default_factory=dict, description="Extracted fields specific to the task type")
    raw_prompt: str = Field(default="", description="Original prompt for debugging")


# ---------------------------------------------------------------------------
# Field specs per task type: required / optional fields + sub-schemas
# ---------------------------------------------------------------------------

TASK_FIELD_SPECS: dict[TaskType, dict] = {
    # ── Tier 1 ─────────────────────────────────────────────────────────────
    TaskType.CREATE_EMPLOYEE: {
        "required": ["first_name", "last_name"],
        "optional": [
            "email", "phone", "date_of_birth",
            "department_name", "employee_number", "national_identity_number",
            "address_line1", "postal_code", "city",
            "bank_account_number", "user_type",
        ],
    },
    TaskType.UPDATE_EMPLOYEE: {
        "required": ["employee_identifier"],  # name, number, or email to look up
        "optional": [
            "first_name", "last_name", "email", "phone",
            "date_of_birth", "department_name", "address_line1",
            "postal_code", "city", "bank_account_number",
        ],
    },
    TaskType.DELETE_EMPLOYEE: {
        "required": ["employee_identifier"],
        "optional": [],
    },
    TaskType.SET_EMPLOYEE_ROLES: {
        "required": ["employee_identifier", "user_type"],
        "optional": ["allow_information_registration"],
    },
    TaskType.CREATE_CUSTOMER: {
        "required": ["name"],
        "optional": [
            "email", "phone", "organization_number", "invoice_email",
            "address_line1", "postal_code", "city", "country",
            "is_private_individual", "language", "invoice_send_method",
            "invoices_due_in", "invoices_due_in_type",
            "customer_number", "discount_percentage", "website",
        ],
    },
    TaskType.UPDATE_CUSTOMER: {
        "required": ["customer_identifier"],  # name, number, or org number
        "optional": [
            "name", "email", "phone", "organization_number",
            "invoice_email", "address_line1", "postal_code", "city",
            "is_private_individual", "language", "invoice_send_method",
        ],
    },
    TaskType.CREATE_PRODUCT: {
        "required": ["name"],
        "optional": [
            "number", "description", "price_excluding_vat",
            "price_including_vat", "cost_excluding_vat",
            "vat_type_id", "vat_percentage", "unit", "currency", "is_stock_item",
            "ean", "weight", "weight_unit", "department_name",
        ],
    },
    TaskType.UPDATE_PRODUCT: {
        "required": ["name"],
        "optional": ["price", "vat_type", "number"],
    },
    TaskType.DELETE_PRODUCT: {
        "required": ["name"],
        "optional": ["product_number"],
    },
    TaskType.CREATE_INVOICE: {
        "required": ["customer_name", "lines"],
        "optional": [
            "invoice_date", "due_date", "comment", "currency",
            "send_to_customer", "order_number",
        ],
        "lines_fields": {
            "required": [],
            "optional": [
                "product_name", "number", "description", "quantity",
                "unit_price", "unit_price_including_vat",
                "discount", "vat_type_id",
            ],
        },
    },
    TaskType.CREATE_DEPARTMENT: {
        "required": ["name"],
        "optional": ["department_number", "manager_name"],
    },
    TaskType.CREATE_PROJECT: {
        "required": ["name"],
        "optional": [
            "number", "description", "start_date", "end_date",
            "customer_name", "project_manager_name", "department_name",
            "is_internal", "is_fixed_price", "fixed_price",
            "project_category_name",
        ],
    },

    # ── Tier 2 ─────────────────────────────────────────────────────────────
    TaskType.INVOICE_EXISTING_CUSTOMER: {
        "required": ["customer_identifier", "lines"],
        "optional": [
            "invoice_date", "due_date", "comment", "currency",
            "send_to_customer",
        ],
        "lines_fields": {
            "required": [],
            "optional": [
                "product_name", "number", "description", "quantity",
                "unit_price", "unit_price_including_vat",
                "discount", "vat_type_id",
            ],
        },
    },
    TaskType.REGISTER_PAYMENT: {
        "required": ["invoice_identifier", "amount"],
        "optional": ["payment_date", "payment_type"],
    },
    TaskType.CREATE_CREDIT_NOTE: {
        "required": ["invoice_identifier"],
        "optional": ["comment", "credit_note_date"],
    },
    TaskType.INVOICE_WITH_PAYMENT: {
        "required": ["customer_name", "lines", "paid_amount"],
        "optional": [
            "invoice_date", "due_date", "comment", "currency",
            "payment_type",
        ],
        "lines_fields": {
            "required": [],
            "optional": [
                "product_name", "number", "description", "quantity",
                "unit_price", "unit_price_including_vat",
                "discount", "vat_type_id",
            ],
        },
    },
    TaskType.CREATE_TRAVEL_EXPENSE: {
        "required": ["employee_identifier"],
        "optional": [
            "title", "project_name", "department_name",
            "departure_date", "return_date", "departure_from",
            "destination", "departure_time", "return_time", "purpose",
            "is_day_trip", "is_foreign_travel",
            "costs",  # list of {date, amount, category, payment_type}
            "mileage_allowances",  # list of {date, km, from, to, rate_type}
            "per_diem_compensations",  # list of {count, location, rate_type}
        ],
    },
    TaskType.DELETE_TRAVEL_EXPENSE: {
        "required": ["travel_expense_identifier"],  # number, title, or employee+date
        "optional": [],
    },
    TaskType.PROJECT_WITH_CUSTOMER: {
        "required": ["project_name", "customer_identifier"],
        "optional": [
            "project_number", "description", "start_date", "end_date",
            "project_manager_name", "is_fixed_price", "fixed_price",
        ],
    },
    TaskType.PROJECT_BILLING: {
        "required": ["project_identifier", "lines"],
        "optional": ["invoice_date", "due_date", "comment"],
        "lines_fields": {
            "required": [],
            "optional": [
                "product_name", "number", "description", "quantity",
                "unit_price", "unit_price_including_vat",
            ],
        },
    },
    TaskType.CREATE_CONTACT: {
        "required": ["first_name", "last_name", "customer_identifier"],
        "optional": ["email", "phone", "department_name"],
    },
    TaskType.FIND_CUSTOMER: {
        "required": ["search_query"],  # name, org number, email, etc.
        "optional": ["search_field"],  # which field to search
    },
    TaskType.UPDATE_PROJECT: {
        "required": ["project_identifier"],  # name, number, or ID
        "optional": [
            "new_name", "new_description", "new_start_date", "new_end_date",
            "is_closed", "project_manager_name", "department_name",
            "is_fixed_price", "fixed_price",
        ],
    },
    TaskType.DELETE_PROJECT: {
        "required": ["project_identifier"],  # name, number, or ID
        "optional": [],
    },
    TaskType.LOG_HOURS: {
        "required": ["employee_identifier", "project_name", "hours"],
        "optional": [
            "activity_name", "date", "comment",
            "employee_email", "first_name", "last_name",
        ],
    },

    TaskType.DELETE_CUSTOMER: {
        "required": ["customer_identifier"],  # name, number, or org number
        "optional": [],
    },
    TaskType.UPDATE_CONTACT: {
        "required": ["contact_identifier", "customer_identifier"],
        "optional": [
            "new_first_name", "new_last_name", "new_email", "new_phone",
            "first_name", "last_name", "email", "phone",
        ],
    },
    TaskType.UPDATE_DEPARTMENT: {
        "required": ["department_identifier"],  # name or number
        "optional": [
            "new_name", "new_department_number", "manager_name",
        ],
    },
    TaskType.CREATE_SUPPLIER_INVOICE: {
        "required": ["supplier_name"],
        "optional": [
            "organization_number", "invoice_number", "amount_including_vat",
            "amount_excluding_vat", "vat_amount", "vat_percentage",
            "invoice_date", "due_date", "description", "account_number",
        ],
    },
    TaskType.CREATE_SUPPLIER: {
        "required": ["name"],
        "optional": [
            "organization_number", "email", "phone",
            "address_line1", "postal_code", "city",
            "bank_account_number", "supplier_number",
        ],
    },
    TaskType.UPDATE_SUPPLIER: {
        "required": ["name"],
        "optional": ["org_number", "bank_account"],
    },
    TaskType.DELETE_SUPPLIER: {
        "required": ["name"],
        "optional": ["supplier_number"],
    },
    TaskType.FIND_SUPPLIER: {
        "required": ["name"],
        "optional": ["org_number"],
    },
    TaskType.DELETE_DEPARTMENT: {
        "required": ["name"],
        "optional": ["department_number"],
    },
    TaskType.RUN_PAYROLL: {
        "required": ["employee_identifier"],
        "optional": [
            "base_salary", "bonus", "month", "year",
            "first_name", "last_name", "email",
            "deductions", "description",
        ],
    },
    TaskType.REVERSE_PAYMENT: {
        "required": ["customer_name"],
        "optional": [
            "organization_number", "invoice_number", "invoice_identifier",
            "amount", "amount_excluding_vat", "reason",
        ],
    },

    # ── Tier 3 ─────────────────────────────────────────────────────────────
    TaskType.BANK_RECONCILIATION: {
        "required": [],  # details come from file
        "optional": [
            "account_number", "period_start", "period_end",
            "transactions",  # parsed from CSV/file
        ],
    },
    TaskType.ERROR_CORRECTION: {
        "required": ["voucher_identifier"],
        "optional": ["correction_description", "new_postings"],
    },
    TaskType.YEAR_END_CLOSING: {
        "required": ["year"],
        "optional": [],
    },
    TaskType.ENABLE_MODULE: {
        "required": ["module_name"],
        "optional": [],
    },
    TaskType.CREATE_DIMENSION_VOUCHER: {
        "required": ["dimension_name"],
        "optional": [
            "dimension_values", "account_number", "contra_account_number",
            "amount", "linked_dimension_value", "description", "voucher_date",
        ],
    },

    # ── Fallback ───────────────────────────────────────────────────────────
    TaskType.UNKNOWN: {
        "required": [],
        "optional": [],
    },
}


# ---------------------------------------------------------------------------
# Descriptions for the classifier prompt — one line per task type
# ---------------------------------------------------------------------------

TASK_TYPE_DESCRIPTIONS: dict[TaskType, str] = {
    TaskType.CREATE_EMPLOYEE: "Create a new employee in the system",
    TaskType.UPDATE_EMPLOYEE: "Update an existing employee's details (name, email, phone, address, etc.)",
    TaskType.DELETE_EMPLOYEE: "Delete/remove an existing employee",
    TaskType.SET_EMPLOYEE_ROLES: "Set or change an employee's user type / access role",
    TaskType.CREATE_CUSTOMER: "Create a new customer",
    TaskType.UPDATE_CUSTOMER: "Update an existing customer's details",
    TaskType.CREATE_PRODUCT: "Create a new product or service",
    TaskType.UPDATE_PRODUCT: "Update an existing product's details (name, price, VAT type, etc.)",
    TaskType.DELETE_PRODUCT: "Delete/remove an existing product",
    TaskType.CREATE_INVOICE: "Create an invoice for a customer (may include creating a new customer inline)",
    TaskType.CREATE_DEPARTMENT: "Create a new department",
    TaskType.CREATE_PROJECT: "Create a new project",
    TaskType.INVOICE_EXISTING_CUSTOMER: "Create an invoice for an already-existing customer (look up by name/number)",
    TaskType.REGISTER_PAYMENT: "Register a payment on an existing invoice",
    TaskType.CREATE_CREDIT_NOTE: "Create a credit note for an existing invoice",
    TaskType.INVOICE_WITH_PAYMENT: "Create an invoice AND register payment for it in one go",
    TaskType.CREATE_TRAVEL_EXPENSE: "Create a travel expense / reiseregning",
    TaskType.DELETE_TRAVEL_EXPENSE: "Delete an existing travel expense",
    TaskType.PROJECT_WITH_CUSTOMER: "Create a project linked to an existing customer",
    TaskType.PROJECT_BILLING: "Invoice a project (create invoice from project work)",
    TaskType.CREATE_CONTACT: "Create a contact person for an existing customer",
    TaskType.FIND_CUSTOMER: "Search for / find a customer by name, org number, or other criteria",
    TaskType.UPDATE_PROJECT: "Update an existing project's details (name, dates, status, etc.)",
    TaskType.DELETE_PROJECT: "Delete/remove an existing project",
    TaskType.LOG_HOURS: "Log/register hours or time entries on a project activity (timesheet entry)",
    TaskType.DELETE_CUSTOMER: "Delete/remove an existing customer",
    TaskType.UPDATE_CONTACT: "Update an existing contact person's details (name, email, phone)",
    TaskType.UPDATE_DEPARTMENT: "Update an existing department's details (name, number, manager)",
    TaskType.CREATE_SUPPLIER_INVOICE: "Register an incoming supplier invoice (leverandørfaktura / inngående faktura)",
    TaskType.CREATE_SUPPLIER: "Register/create a new supplier (leverandør / Lieferant / fournisseur)",
    TaskType.UPDATE_SUPPLIER: "Update an existing supplier's details (name, org number, bank account)",
    TaskType.DELETE_SUPPLIER: "Delete/remove an existing supplier",
    TaskType.FIND_SUPPLIER: "Search for / find a supplier by name or org number",
    TaskType.DELETE_DEPARTMENT: "Delete/remove an existing department",
    TaskType.RUN_PAYROLL: "Run payroll / create salary payment for an employee (lønn / paie / Gehalt / nómina)",
    TaskType.REVERSE_PAYMENT: "Reverse a payment that was returned/bounced by the bank, reopening the invoice as outstanding",
    TaskType.BANK_RECONCILIATION: "Reconcile bank transactions (often from a CSV file)",
    TaskType.ERROR_CORRECTION: "Correct an error in the ledger (reverse or adjust a voucher)",
    TaskType.YEAR_END_CLOSING: "Perform year-end closing procedures",
    TaskType.ENABLE_MODULE: "Enable a company module or feature in Tripletex",
    TaskType.CREATE_DIMENSION_VOUCHER: "Create a custom accounting dimension with values, and optionally post a voucher linked to a dimension value",
    TaskType.UNKNOWN: "Could not determine the task type — use fallback logic",
}
