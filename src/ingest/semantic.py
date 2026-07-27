"""Semantic metadata for schema columns: descriptions + synonyms.

Rule-based fallback ensures schema-agnostic enrichment without requiring
an LLM provider. Optional LLM enrichment is used when a provider key is
configured; otherwise the rule-based metadata is used.
"""
from __future__ import annotations

import json
import re
from typing import Any


# Keyword-driven mappings for common police/data terms.
_DESCRIPTION_MAP: dict[str, str] = {
    "reg_dt": "Registration datetime of the FIR/case",
    "reg_num": "Registration identifier/number",
    "fir_reg_num": "Unique FIR registration number/ID",
    "fir_no": "FIR number assigned to the complaint",
    "fir_number": "FIR number assigned to the complaint",
    "fir_num": "FIR number assigned to the complaint",
    "district": "District where the incident was registered",
    "zone": "Police zone/division",
    "range": "Police range area",
    "state": "State/region",
    "ps_name": "Police station name",
    "police_station": "Police station name",
    "station_name": "Police station name",
    "crime_head": "Primary crime/category description",
    "crime_category": "High-level crime grouping/category",
    "act_code": "Penal act/section code",
    "penal_section": "Penal section invoked in the FIR",
    "status": "Current status of the FIR/case",
    "victim_count": "Count of victims",
    "accused_count": "Count of accused persons",
    "property_value": "Estimated property value involved",
    "chargesheet": "Whether chargesheet was filed",
    "disposal": "Case disposal flag/status",
    "pending": "Pending case indicator",
    "gender": "Gender category",
    "age": "Age of the person",
    "address": "Address text",
    "mobile": "Mobile contact number",
    "phone": "Contact phone number",
    "aadhaar": "Aadhaar identity number",
    "pan": "PAN identity/tax identifier",
    "dob": "Date of birth",
    "registration_number": "Registration identifier/number",
    "registration": "Registration identifier",
    "act": "Act/section under which case is registered",
    "section": "Legal section/code",
    "date_of_registration": "Date when FIR was registered",
    "incident_date": "Date of the reported incident",
    "date": "Date value",
    "time": "Time value",
    "created_at": "Record creation timestamp",
    "updated_at": "Record update timestamp",
    "count": "Count/aggregate value",
    "total": "Total numeric value",
    "amount": "Monetary amount/value",
    "value": "Numeric value/measure",
    "salary": "Salary amount",
    "revenue": "Revenue amount",
    "karma_points": "Officer engagement and activity score",
    "course_completions": "Number of learning courses completed",
    "event_completions": "Number of training events completed",
    "total_learning_hours": "Total hours of training completed",
    "designation": "Role or rank descriptor",
    "group": "Officer service group (A/B/C/D)",
}


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


_SYNONYMS: dict[str, tuple[str, ...]] = {
    "reg_dt": ("registration date", "fir date", "case date", "incident date", "date of registration", "date and time"),
    "reg_num": ("registration number", "fir id", "case number", "record number"),
    "fir_reg_num": ("fir number", "registration number", "fir id", "fir no", "case number", "complaint number"),
    "fir_no": ("fir number", "fir id", "registration number", "case number"),
    "fir_number": ("fir number", "registration number", "fir id", "case number", "complaint number"),
    "district": ("district name", "location", "area", "jurisdiction", "place"),
    "zone": ("zone name", "division", "cluster", "circle"),
    "range": ("range name", "circle", "division"),
    "state": ("state name", "province", "region"),
    "ps_name": ("police station", "station", "thana", "unit", "police station name"),
    "crime_head": ("crime", "offence", "offense", "crime type", "crime category", "category"),
    "crime_category": ("crime group", "major crime", "crime class"),
    "act_code": ("act", "section", "law", "legal section", "penal section"),
    "penal_section": ("section", "act", "law", "legal code"),
    "status": ("case status", "disposal status", "current status"),
    "victim_count": ("victims", "no of victims", "number of victims"),
    "accused_count": ("accused", "no of accused", "number of accused"),
    "property_value": ("property loss", "value", "loss amount", "damage value"),
    "chargesheet": ("charge sheet", "final report", "chargesheet filed"),
    "disposal": ("disposed", "disposal status", "case closed"),
    "pending": ("undecided", "open", "not disposed", "pending case"),
    "gender": ("sex", "male/female/other", "gender category"),
    "age": ("age in years", "years"),
    "mobile": ("contact number", "phone number", "cell number"),
    "aadhaar": ("uid", "identity number", "aadhaar number"),
    "pan": ("pan number", "tax id", "permanent account number"),
    "date": ("date", "day", "calendar date"),
    "time": ("timestamp", "hour", "time of day"),
    "created_at": ("created", "inserted at", "logged at"),
    "karma_points": ("activity score", "officer engagement", "karma"),
    "course_completions": ("learning completions", "courses done"),
    "event_completions": ("training completions", "events done"),
    "total_learning_hours": ("training hours", "learning time", "hours"),
    "designation": ("role", "rank", "position"),
    "group": ("service group", "category group", "grouping"),
}

_GENERIC_DESCRIPTION_MAP: dict[str, str] = {
    "amount": "Monetary amount/value",
    "total": "Total numeric value",
    "revenue": "Revenue amount",
    "name": "Name field",
    "category": "Category/group label",
    "status": "Current status",
    "region": "Region/area name",
    "department": "Department name",
    "employee": "Employee name/id",
    "product": "Product name/id",
    "order": "Order identifier",
    "customer": "Customer name/id",
    "city": "City name",
    "country": "Country name",
    "address": "Address text",
    "email": "Email address",
    "phone": "Phone number",
    "salary": "Salary amount",
    "discount": "Discount amount/rate",
    "profit": "Profit value",
    "quantity": "Quantity/count",
    "price": "Price value",
    "cost": "Cost value",
    "tax": "Tax amount",
    "rating": "Rating value",
    "feedback": "Feedback text",
    "url": "URL/link",
    "description": "Description text",
    "priority": "Priority level",
    "type": "Type/category label",
    "source": "Source system/name",
    "target": "Target system/name",
    "start_date": "Start date",
    "end_date": "End date",
    "created_by": "Created by user",
    "updated_by": "Updated by user",
    "manager": "Manager name",
    "id": "Unique identifier",
}

_GENERIC_SYNONYMS: dict[str, tuple[str, ...]] = {
    "amount": ("amt", "monetary value", "price", "charge"),
    "total": ("sum", "aggregate", "overall"),
    "revenue": ("income", "earnings", "turnover"),
    "name": ("full name", "label", "title"),
    "category": ("type", "group", "class"),
    "status": ("state", "condition", "stage"),
    "region": ("area", "territory", "zone", "division"),
    "department": ("dept", "unit", "team"),
    "employee": ("staff", "worker", "personnel"),
    "product": ("item", "goods", "service"),
    "order": ("purchase", "sale", "transaction"),
    "customer": ("client", "buyer", "purchaser"),
    "city": ("town", "municipality"),
    "country": ("nation", "land"),
    "address": ("location", "addr"),
    "email": ("e-mail", "mail", "email address"),
    "phone": ("telephone", "mobile", "contact"),
    "salary": ("wage", "pay", "compensation"),
    "discount": ("markdown", "reduction"),
    "profit": ("net", "margin", "gain"),
    "quantity": ("qty", "volume", "count"),
    "price": ("cost", "rate", "unit price"),
    "cost": ("expense", "price"),
    "tax": ("gst", "vat", "duty"),
    "rating": ("score", "rank", "stars"),
    "feedback": ("review", "comment", "remark"),
    "url": ("link", "web address"),
    "description": ("details", "info", "text"),
    "priority": ("importance", "severity", "urgency"),
    "type": ("kind", "class", "group"),
    "source": ("origin", "from"),
    "target": ("destination", "to"),
    "start_date": ("from date", "begin date"),
    "end_date": ("to date", "close date"),
    "created_by": ("creator", "owner", "added by"),
    "updated_by": ("modifier", "editor", "changed by"),
    "manager": ("supervisor", "lead", "head"),
    "id": ("identifier", "key", "pk"),
}


def _rule_description(name: str) -> str:
    key = _normalize(name)
    if key in _DESCRIPTION_MAP:
        return _DESCRIPTION_MAP[key]
    if key in _GENERIC_DESCRIPTION_MAP:
        return _GENERIC_DESCRIPTION_MAP[key]
    low = name.lower()
    if low.endswith("_id") or low.startswith("id"):
        return "Unique identifier for " + name
    if low.endswith("_at"):
        return "Timestamp for " + name
    if low.endswith("_dt"):
        return "DateTime value for " + name
    if "count" in low or "total" in low:
        return "Count or total metric"
    if "amount" in low or "value" in low:
        return "Numeric amount/value"
    if "date" in low or "time" in low:
        return "Date or time value"
    if "name" in low:
        return "Name field"
    if "code" in low or "section" in low:
        return "Code or section identifier"
    return "Field: " + name


def _rule_synonyms(name: str) -> list[str]:
    key = _normalize(name)
    if key in _SYNONYMS:
        return list(_SYNONYMS[key])
    if key in _GENERIC_SYNONYMS:
        return list(_GENERIC_SYNONYMS[key])
    low = name.lower()
    syns = [low]
    if "_" in low:
        syns.append(low.replace("_", " "))
    return syns


def _llm_enrich(column_name: str, column_type: str | None, sample_values: list[str] | None = None, context: str = "generic dataset") -> dict[str, Any] | None:
    try:
        from src.config.settings import get_settings
        settings = get_settings()
        if not settings.key_for(settings.resolve_provider()):
            return None

        from src.llm.client import LLMClient
        client = LLMClient()
        system = (
            "You are a data dictionary assistant. Given one column from a dataset, "
            "return JSON with `description`, `synonyms`, `domain_type`, and `pii_likely`."
        )
        sample_text = ""
        if sample_values:
            sample_text = "Sample values:\n" + "\n".join(f"- {v}" for v in sample_values[:5])
        user = (
            "Context: {ctx}\n"
            "Column name: {name}\n"
            "Column type: {ctype}\n"
            "{sample_text}\n\n"
            "Return ONLY JSON like:\n"
            "{{\"description\":\"...\",\"synonyms\":[\"...\"],\"domain_type\":\"categorical|numeric|date|text|boolean\",\"pii_likely\":true|false}}\n"
        ).format(ctx=context, name=column_name, ctype=column_type or "unknown", sample_text=sample_text)
        raw = client.complete(system, user, max_tokens=300).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        desc = data.get("description")
        syns = data.get("synonyms")
        if not isinstance(desc, str) or not isinstance(syns, list):
            return None
        out: dict[str, Any] = {"description": desc.strip(), "synonyms": [str(s) for s in syns if str(s).strip()]}
        domain_type = data.get("domain_type")
        if isinstance(domain_type, str) and domain_type.strip():
            out["domain_type"] = domain_type.strip()
        pii_likely = data.get("pii_likely")
        if isinstance(pii_likely, bool):
            out["pii_likely"] = pii_likely
        return out
    except Exception:
        return None


def enrich_schema(schema: list[dict[str, Any]], use_llm: bool = True, sample_lookup: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    enriched = []
    for col in schema:
        name = col.get("name") or ""
        ctype = col.get("type")
        rule_desc = _rule_description(name)
        generic_rule = rule_desc == ("Field: " + name)
        meta: dict[str, Any] | None = None
        if use_llm and generic_rule:
            vals = []
            if isinstance(sample_lookup, dict):
                vals = [str(v) for v in sample_lookup.get(name, []) if v is not None]
            meta = _llm_enrich(name, ctype, sample_values=vals)
        if not meta:
            meta = {
                "description": rule_desc,
                "synonyms": _rule_synonyms(name),
            }
        item = dict(col)
        item["description"] = meta.get("description") or rule_desc
        item["synonyms"] = meta.get("synonyms") or _rule_synonyms(name)
        enriched.append(item)
    return enriched
