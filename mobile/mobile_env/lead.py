import functools
import json
import os
import calendar
import frappe
from frappe import _
from bs4 import BeautifulSoup
from frappe.utils import cstr, now, today
from frappe.utils import (
    cstr,
    get_date_str,
    today,
    nowdate,
    getdate,
    now_datetime,
    get_first_day,
    get_last_day,
    date_diff,
    flt,
    pretty_date,
    fmt_money,
)
from frappe.utils.data import nowtime
from mobile.mobile_env.app_utils import (
    gen_response,
    generate_key,
    role_profile,
    ess_validate,
    get_employee_by_user,
    validate_employee_data,
    get_ess_settings,
    get_global_defaults,
    exception_handel,
)
from frappe.utils import getdate, get_url
import requests
import json
from mobile.mobile_env.location import add_user_location



@frappe.whitelist()
def lead_details():
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        if not emp_data:
            return gen_response(500, "Employee not found for this user.")
        if not frappe.has_permission("Lead", "read"):
            return gen_response(403, _("Not permitted"))
        meta_data={}
        meta_data["territory"]=frappe.get_list("Territory",pluck="name",filters={"is_group":0})
        meta_data["lead_source"]=frappe.get_list("Lead Source",pluck="name")
        meta_data["industry_type"]=frappe.get_list("Industry Type",pluck="name")
        meta_data["customer"]=frappe.get_list("Customer",pluck="name",filters={"disabled":0})
        meta_data["project"]=frappe.get_list("Project",pluck="name")
        meta_data["lead_type"]=frappe.get_list("Market Segment",pluck="name")
        gen_response(200, "Lead data fetched successfully", meta_data)
    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist()
def project_lead_details():
    try:
        meta_data={}
        meta_data["territory"]=frappe.get_list("Territory",pluck="name",filters={"is_group":0})
        meta_data["project_lead_type"]=frappe.get_list("Project Lead Type",pluck="name")
        meta_data["project_plan"]=frappe.get_list("Project Plan",pluck="name")
        meta_data["site_status"]=frappe.get_list("Project Site Status",pluck="name")
        gen_response(200, "Lead data fetched successfully", meta_data)
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def marketing_details():
    try:
        meta_data={}
        meta_data["customer"]=frappe.get_list("Customer",pluck="name",filters={"disabled":0})
        meta_data["merchandise_items"]=frappe.get_list("Item",fields=["name","uom","item_name"],filters={"disabled":0,"item_group":"Merchandise"})
        gen_response(200, "Merchandise data fetched successfully", meta_data)
    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist()
def get_lead_details(lead):
    try:
        if not lead:
            return gen_response(400, "Lead ID is required")

        # Validate employee mapping
        emp_data = get_employee_by_user(frappe.session.user)
        if not emp_data:
            return gen_response(404, "Employee not found for this user")

        # Permission check (doc-level)
        if not frappe.has_permission("Lead", "read", doc=lead):
            return gen_response(403, "Not permitted to view this Lead")

        # Fetch lead
        lead_doc = frappe.get_doc("Lead", lead)

        # Convert to dict (safe for API)
        lead_data = lead_doc.as_dict()

        # Resolve image URL
        lead_data["image"] = (
            frappe.utils.get_url(lead_doc.image)
            if lead_doc.image else None
        )

        return gen_response(
            200,
            "Lead data fetched successfully",
            lead_data
        )

    except frappe.DoesNotExistError:
        return gen_response(404, "Lead not found")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_lead_details error")
        return exception_handel(e)

    
    
import frappe
from frappe.utils import nowdate
import base64
import frappe
from frappe.utils import nowdate
from frappe.utils.file_manager import save_file

@frappe.whitelist(allow_guest=True)
def create_lead(**kwargs):
    try:
        data = frappe._dict(kwargs)

        # -------------------------
        # CREATE OR UPDATE LEAD
        # -------------------------
        if data.get("name"):
            if not frappe.db.exists("Lead", data.name):
                return gen_response(404, "Invalid Lead ID")
            lead_doc = frappe.get_doc("Lead", data.name)
            msg = "Lead updated successfully"
        else:
            lead_doc = frappe.new_doc("Lead")
            msg = "Lead created successfully"

        # -------------------------
        # FIELD MAPPING
        # -------------------------
        standard_fields = [
            "lead_name", "first_name", "company_name", "email_id",
            "mobile_no", "phone", "source", "type",
            "request_type", "lead_owner", "territory",
            "language", "company", "title","market_segment"
        ]

        custom_fields = [
            "custom_date", "custom_call_status", "custom_description",
            "custom_pincode", "custom_latitude", "custom_longitude","custom_location_address",
            "qualification_status", "no_of_employees","custom_address","custom_gst_in",
            "annual_revenue", "industry", "city", "state", "country"
        ]

        # -------------------------
        # SET STANDARD FIELDS
        # -------------------------
        for field in standard_fields:
            if field in data:
                if field == "mobile_no" and not data.get("mobile_no"):
                    lead_doc.mobile_no = data.get("phone")
                elif field == "lead_owner" and not data.get("lead_owner"):
                    lead_doc.lead_owner = frappe.session.user
                else:
                    setattr(lead_doc, field, data.get(field))

        # -------------------------
        # SET CUSTOM FIELDS
        # -------------------------
        for field in custom_fields:
            if field in data:
                setattr(lead_doc, field, data.get(field))
        address = get_address_from_lat_long(data.get("custom_latitude"),data.get("custom_longitude"))
        if address:
            setattr(lead_doc, "custom_location_address", address)
        # -------------------------
        # SAVE LEAD FIRST (IMPORTANT)
        # -------------------------
        frappe.log_error(message=frappe.as_json(lead_doc), title="Lead Doc Data")
        if data.get("name"):
            lead_doc.save(ignore_permissions=True)
        else:
            lead_doc.insert(ignore_permissions=True)

        # -------------------------
        # HANDLE IMAGE (MULTIPART FILE)
        # -------------------------
        if frappe.request.files.get("image"):
            image = frappe.request.files["image"]
            file_content = image.stream.read()

            file_doc = save_file(
                image.filename,
                file_content,
                lead_doc.doctype,
                lead_doc.name,
                decode=False,
                is_private=0
            )

            # Set image field on Lead
            frappe.db.set_value(
                "Lead",
                lead_doc.name,
                "image",
                file_doc.file_url
            )

        # -------------------------
        # ADD USER LOCATION
        # -------------------------
        if lead_doc.custom_latitude and lead_doc.custom_longitude:
            location_dict = {
            "lat":lead_doc.custom_latitude,
            "lng":lead_doc.custom_longitude,
            "reference_type": "Lead",
            "reference_name": lead_doc.name,
            "date": nowdate()
            }

            frappe.enqueue(
                "mobile.mobile_env.location.add_user_location",
                queue="short",
                timeout=60,
                **location_dict
            )

        return gen_response(
            200,
            msg,
            {
                "lead_id": lead_doc.name,
                "image": lead_doc.image
            }
        )

    except Exception as e:
        return exception_handel(e)


import requests

def get_address_from_lat_long_google(latitude, longitude):
    if not latitude or not longitude:
        return ""

    google_key = "AIzaSyCVZOsMk8EilxhjhdRXFfmbrnVE58_wjik"
    if google_key:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "latlng": f"{latitude},{longitude}",
            "key": google_key,
        }
        headers = {
            "User-Agent": "Frappe-App/1.0",
        }
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            frappe.log_error(message=f"Google Reverse Geocoding Response: {data}", title="get_address_from_lat_long")
            if data.get("status") == "OK" and data.get("results"):
                formatted = data["results"][0].get("formatted_address")
                if formatted:
                    return formatted
            return ""
        except Exception:
            return ""

def get_address_from_lat_long(latitude, longitude):
    if not latitude or not longitude:
        return ""

    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "json",
        "addressdetails": 1,
        "zoom": 18,
        "email": os.getenv("NOMINATIM_EMAIL", "contact@yourdomain.com"),
    }
    headers = {
        "User-Agent": "Frappe-App/1.0 (contact@yourdomain.com)",
        "Referer": get_url(),
    }

    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        frappe.log_error(message=f"Reverse Geocoding Response: {data}", title="get_address_from_lat_long")
        display_name = data.get("display_name")
        if display_name:
            return display_name

        address = data.get("address", {})
        address_line = build_address_line(address)

        return address_line

    except Exception as e:
        return ""


def build_address_line(address_data: dict):
    if not address_data or not isinstance(address_data, dict):
        return ""

    parts = [
        address_data.get("house_name"),
        address_data.get("house_number"),
        address_data.get("building"),
        address_data.get("residential"),
        address_data.get("amenity"),
        address_data.get("road"),
        address_data.get("neighbourhood"),
        address_data.get("suburb"),
        address_data.get("hamlet"),
        address_data.get("village"),
        address_data.get("town"),
        address_data.get("city"),
        address_data.get("tehsil"),
        address_data.get("district"),
        address_data.get("county"),
        address_data.get("state_district"),
        address_data.get("state"),
        address_data.get("postcode"),
        address_data.get("country"),
    ]

    # remove None / empty values
    clean_parts = [str(p).strip() for p in parts if p and str(p).strip()]

    # join with comma
    return ", ".join(clean_parts)
