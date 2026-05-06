"""
First-party plugin: Fakturoid Invoicing (v1.1)

Integrates with the Czech invoicing service Fakturoid to create invoices
or quotations directly from LeadLab's proposals.

Configuration (stored in PluginConfig.config):
  slug          : str   — Fakturoid account slug (found in your Fakturoid URL)
  email         : str   — Email address used to log in to Fakturoid
  api_token     : str   — Fakturoid API token (secret; found in Fakturoid → Settings → API)
  document_type : str   — "invoice" (default) or "quotation" — type of document created from proposals
  auto_send     : bool  — If true, automatically deliver the document by e-mail after creation
                          (requires the contact to have an e-mail address set)

Fakturoid API v2 docs: https://fakturoid.docs.apiary.io/
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

from leadlab.plugin_registry import LeadLabPlugin, register

logger = logging.getLogger(__name__)

FAKTUROID_API_BASE = "https://app.fakturoid.cz/api/v2/accounts"


class FakturoidPlugin(LeadLabPlugin):
    manifest = {
        "name": "fakturoid",
        "version": "1.1.0",
        "description": (
            "Integrates with the Czech invoicing service Fakturoid. "
            "Create invoices or quotations directly from proposals."
        ),
        "icon_url": "https://cdn.leadlab.io/plugins/fakturoid/icon.png",
        "permissions": ["records:read"],
        "activity_types": [],
        "webhook_event_types": [],
        "config_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "title": "Account Slug",
                    "description": (
                        "Fakturoid account slug (e.g. 'my-company'). "
                        "Found in your Fakturoid URL: app.fakturoid.cz/api/v2/accounts/<slug>/"
                    ),
                },
                "email": {
                    "type": "string",
                    "title": "Email",
                    "description": "Email address used to log in to Fakturoid.",
                },
                "api_token": {
                    "type": "string",
                    "title": "API Token",
                    "description": "Fakturoid API token (found in Fakturoid → Settings → API).",
                    "secret": True,
                },
                "document_type": {
                    "type": "string",
                    "title": "Typ dokladu pro Nabídky",
                    "description": (
                        "Vyberte, zda se z LeadLab nabídek mají v Fakturoidu vytvářet "
                        "'invoice' (faktura) nebo 'quotation' (cenová nabídka)."
                    ),
                    "enum": ["invoice", "quotation"],
                    "default": "invoice",
                },
                "auto_send": {
                    "type": "boolean",
                    "title": "Automaticky odeslat po vytvoření",
                    "description": (
                        "Pokud je zapnuto, Fakturoid nabídku/fakturu ihned odešle zákazníkovi "
                        "e-mailem. Kontakt musí mít vyplněný e-mail."
                    ),
                    "default": False,
                },
            },
            "required": ["slug", "email", "api_token"],
        },
    }

    def ready(self) -> None:
        logger.info("FakturoidPlugin ready")

    # ------------------------------------------------------------------
    # Public helpers — called from API endpoints
    # ------------------------------------------------------------------

    @staticmethod
    def get_config(firm_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the Fakturoid config dict for *firm_id* or None if not configured.

        Returns a dict with keys: ``slug``, ``email``, ``api_token``,
        ``document_type`` ("invoice" or "quotation", default "invoice"),
        ``auto_send`` (bool, default False).
        Returns None when the plugin is disabled or any required value is missing.
        """
        try:
            from firms.models import PluginConfig
        except Exception:
            return None

        try:
            pc = PluginConfig.objects.get(
                firm_id=firm_id,
                plugin_name="fakturoid",
                enabled=True,
            )
        except PluginConfig.DoesNotExist:
            return None

        cfg = pc.config or {}
        slug = cfg.get("slug", "").strip()
        email = cfg.get("email", "").strip()
        api_token = cfg.get("api_token", "").strip()
        if not (slug and email and api_token):
            return None
        return {
            "slug": slug,
            "email": email,
            "api_token": api_token,
            "document_type": cfg.get("document_type", "invoice"),
            "auto_send": bool(cfg.get("auto_send", False)),
        }

    @staticmethod
    def _auth_header(email: str, api_token: str) -> Dict[str, str]:
        """Return HTTP Basic Auth header for Fakturoid API."""
        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "User-Agent": "LeadLab (support@leadlab.io)",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _api_url(slug: str, path: str) -> str:
        return f"{FAKTUROID_API_BASE}/{slug}/{path}"

    @staticmethod
    def test_connection(firm_id: str) -> dict:
        """
        Test the Fakturoid API connection by fetching account info.

        Returns ``{"ok": True, "name": ...}`` on success or
        ``{"ok": False, "error": ...}`` on failure.
        """
        try:
            import requests
        except ImportError:
            return {"ok": False, "error": "requests library not installed."}

        cfg = FakturoidPlugin.get_config(firm_id)
        if not cfg:
            return {"ok": False, "error": "Fakturoid credentials not configured or plugin is disabled."}

        url = FakturoidPlugin._api_url(cfg["slug"], "account.json")
        try:
            resp = requests.get(
                url,
                headers=FakturoidPlugin._auth_header(cfg["email"], cfg["api_token"]),
                timeout=10,
            )
        except Exception as exc:
            logger.error("Fakturoid test connection error: %s", exc)
            return {"ok": False, "error": "Network error — could not reach Fakturoid API."}

        if resp.status_code == 200:
            data = resp.json()
            return {"ok": True, "name": data.get("name", cfg["slug"])}
        elif resp.status_code == 401:
            return {"ok": False, "error": "Invalid Fakturoid credentials (401 Unauthorized)."}
        elif resp.status_code == 404:
            return {"ok": False, "error": f"Account '{cfg['slug']}' not found (404)."}
        else:
            return {"ok": False, "error": f"Fakturoid API returned HTTP {resp.status_code}."}

    @staticmethod
    def create_invoice(firm_id: str, invoice_data: Dict[str, Any], auto_send: bool = False) -> dict:
        """
        Create an invoice in Fakturoid.

        *invoice_data* should contain:
          - ``currency``        (str, default "CZK")
          - ``payment_method``  (str, default "bank")
          - ``due``             (int days, default 14)
          - ``note``            (str)
          - ``lines``           (list of dicts with name, quantity, unit_name, unit_price, vat_rate)
          - ``subject_id``      (int | None) — Fakturoid internal subject ID
          - ``subject_custom_id`` (str | None) — resolved to subject_id automatically

        When *auto_send* is True the invoice is delivered to the contact by e-mail
        immediately after creation using the Fakturoid fire event API.
        If the fire event fails, ``sent`` is still set to False in the result.

        Returns ``{"ok": True, "invoice": {...}, "sent": bool}`` on success or
        ``{"ok": False, "error": ...}`` on failure.
        """
        try:
            import requests
        except ImportError:
            return {"ok": False, "error": "requests library not installed."}

        cfg = FakturoidPlugin.get_config(firm_id)
        if not cfg:
            return {"ok": False, "error": "Fakturoid credentials not configured or plugin is disabled."}

        headers = FakturoidPlugin._auth_header(cfg["email"], cfg["api_token"])

        # Resolve subject_id from custom_id if needed
        subject_id = invoice_data.get("subject_id")
        subject_custom_id = invoice_data.get("subject_custom_id")
        if not subject_id and subject_custom_id:
            subjects_url = FakturoidPlugin._api_url(cfg["slug"], "subjects.json")
            try:
                resp = requests.get(
                    subjects_url,
                    headers=headers,
                    params={"custom_id": subject_custom_id},
                    timeout=10,
                )
                if resp.status_code == 200:
                    subjects = resp.json()
                    if subjects:
                        subject_id = subjects[0].get("id")
            except Exception as exc:
                logger.error("Fakturoid subject lookup error: %s", exc)
                return {"ok": False, "error": "Could not look up subject in Fakturoid."}

        payload: Dict[str, Any] = {
            "currency": invoice_data.get("currency", "CZK"),
            "payment_method": invoice_data.get("payment_method", "bank"),
            "due": invoice_data.get("due", 14),
            "note": invoice_data.get("note", ""),
            "lines": invoice_data.get("lines", []),
        }
        if subject_id:
            payload["subject_id"] = subject_id

        url = FakturoidPlugin._api_url(cfg["slug"], "invoices.json")
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
        except Exception as exc:
            logger.error("Fakturoid create invoice error: %s", exc)
            return {"ok": False, "error": "Network error — could not reach Fakturoid API."}

        if resp.status_code in (201, 200):
            data = resp.json()
            invoice_id = data.get("id")
            sent = False
            if auto_send and invoice_id:
                sent = FakturoidPlugin._fire_document(
                    cfg, "invoices", invoice_id, headers, requests
                )
            return {
                "ok": True,
                "sent": sent,
                "invoice": {
                    "id": invoice_id,
                    "number": data.get("number", ""),
                    "html_url": data.get("html_url", ""),
                    "pdf_url": data.get("pdf_url"),
                    "total": str(data.get("total", "")),
                },
            }
        else:
            try:
                err_body = resp.json()
                errors = err_body.get("errors", [])
            except Exception:
                errors = []
            logger.error("Fakturoid invoice creation failed with HTTP %s", resp.status_code)
            error_detail = ", ".join(str(e) for e in errors) if errors else f"HTTP {resp.status_code}"
            return {"ok": False, "error": f"Fakturoid returned HTTP {resp.status_code}: {error_detail}"}

    @staticmethod
    def create_quotation(firm_id: str, quotation_data: Dict[str, Any], auto_send: bool = False) -> dict:
        """
        Create a quotation (cenová nabídka) in Fakturoid.

        *quotation_data* accepts the same fields as *invoice_data* in
        :meth:`create_invoice`.

        When *auto_send* is True the quotation is delivered to the contact by
        e-mail immediately after creation using the Fakturoid fire event API.

        Returns ``{"ok": True, "quotation": {...}, "sent": bool}`` on success or
        ``{"ok": False, "error": ...}`` on failure.
        """
        try:
            import requests
        except ImportError:
            return {"ok": False, "error": "requests library not installed."}

        cfg = FakturoidPlugin.get_config(firm_id)
        if not cfg:
            return {"ok": False, "error": "Fakturoid credentials not configured or plugin is disabled."}

        headers = FakturoidPlugin._auth_header(cfg["email"], cfg["api_token"])

        # Resolve subject_id from custom_id if needed
        subject_id = quotation_data.get("subject_id")
        subject_custom_id = quotation_data.get("subject_custom_id")
        if not subject_id and subject_custom_id:
            subjects_url = FakturoidPlugin._api_url(cfg["slug"], "subjects.json")
            try:
                resp = requests.get(
                    subjects_url,
                    headers=headers,
                    params={"custom_id": subject_custom_id},
                    timeout=10,
                )
                if resp.status_code == 200:
                    subjects = resp.json()
                    if subjects:
                        subject_id = subjects[0].get("id")
            except Exception as exc:
                logger.error("Fakturoid subject lookup error: %s", exc)
                return {"ok": False, "error": "Could not look up subject in Fakturoid."}

        payload: Dict[str, Any] = {
            "currency": quotation_data.get("currency", "CZK"),
            "note": quotation_data.get("note", ""),
            "lines": quotation_data.get("lines", []),
        }
        if subject_id:
            payload["subject_id"] = subject_id

        url = FakturoidPlugin._api_url(cfg["slug"], "quotations.json")
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
        except Exception as exc:
            logger.error("Fakturoid create quotation error: %s", exc)
            return {"ok": False, "error": "Network error — could not reach Fakturoid API."}

        if resp.status_code in (201, 200):
            data = resp.json()
            quotation_id = data.get("id")
            sent = False
            if auto_send and quotation_id:
                sent = FakturoidPlugin._fire_document(
                    cfg, "quotations", quotation_id, headers, requests
                )
            return {
                "ok": True,
                "sent": sent,
                "quotation": {
                    "id": quotation_id,
                    "number": data.get("number", ""),
                    "html_url": data.get("html_url", ""),
                    "pdf_url": data.get("pdf_url"),
                    "total": str(data.get("total", "")),
                },
            }
        else:
            try:
                err_body = resp.json()
                errors = err_body.get("errors", [])
            except Exception:
                errors = []
            logger.error("Fakturoid quotation creation failed with HTTP %s", resp.status_code)
            error_detail = ", ".join(str(e) for e in errors) if errors else f"HTTP {resp.status_code}"
            return {"ok": False, "error": f"Fakturoid returned HTTP {resp.status_code}: {error_detail}"}

    @staticmethod
    def _fire_document(cfg: Dict[str, Any], doc_type: str, doc_id: int, headers: Dict[str, str], requests_module) -> bool:
        """
        Fire the 'deliver' event on a Fakturoid document to send it by e-mail.

        Returns True on success, False on failure (logs the error).
        *doc_type* is either ``"invoices"`` or ``"quotations"``.
        """
        fire_url = FakturoidPlugin._api_url(cfg["slug"], f"{doc_type}/{doc_id}/fire.json")
        try:
            fire_resp = requests_module.post(
                fire_url,
                headers=headers,
                params={"event": "deliver"},
                timeout=10,
            )
            if fire_resp.status_code in (200, 201, 204):
                return True
            else:
                logger.warning(
                    "Fakturoid fire event returned HTTP %s for %s",
                    fire_resp.status_code, doc_type,
                )
                return False
        except Exception:
            logger.error("Fakturoid fire event network error for %s", doc_type)
            return False


plugin = FakturoidPlugin()
register(plugin)
