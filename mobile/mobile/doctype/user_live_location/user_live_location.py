# Copyright (c) 2026, Sanpra Software Solution and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.integrations.utils import make_get_request
from hrms.hr.utils import get_distance_between_coordinates


class UserLiveLocation(Document):

	@frappe.whitelist()
	def get_employee_location(self, login_latitude=None, login_longitude=None):
		if not self.user:
			frappe.throw("Please select a User first.")

		login = None
		if login_latitude not in (None, "") and login_longitude not in (None, ""):
			login = {
				"latitude": float(login_latitude),
				"longitude": float(login_longitude),
			}
		else:
			login = frappe.db.get_value(
				"Get Employee Location",
				{"user": frappe.session.user},
				["latitude", "longitude"],
				as_dict=True,
				order_by="modified desc",
			)

		target = frappe.db.get_value(
			"Get Employee Location",
			{"user": self.user},
			["latitude", "longitude"],
			as_dict=True,
			order_by="modified desc",
		)

		user_lat = (target or {}).get("latitude")
		user_lng = (target or {}).get("longitude")
		login_lat = (login or {}).get("latitude")
		login_lng = (login or {}).get("longitude")

		user_address = _reverse_geocode(user_lat, user_lng)
		login_user_address = _reverse_geocode(login_lat, login_lng)

		distance = None
		if (
			user_lat not in (None, "")
			and user_lng not in (None, "")
			and login_lat not in (None, "")
			and login_lng not in (None, "")
		):
			try:
				distance_m = float(
					get_distance_between_coordinates(
						float(user_lat),
						float(user_lng),
						float(login_lat),
						float(login_lng),
					)
				)
				distance = distance_m / 1000
			except Exception:
				frappe.log_error(frappe.get_traceback(), "User Live Location: Distance calculation failed")

		return {
			"user": {
				"latitude": user_lat,
				"longitude": user_lng,
				"address": user_address,
			},
			"login_user": {
				"latitude": login_lat,
				"longitude": login_lng,
				"address": login_user_address,
			},
			"distance": distance,
		}
	
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_users_by_company_permission(doctype, txt, searchfield, start, page_len, filters):
    # Get companies permitted to logged-in user
    companies = frappe.get_all(
        "User Permission",
        filters={
            "user": frappe.session.user,
            "allow": "Company"
        },
        pluck="for_value"
    )

    if not companies:
        return []

    # Get users who have permission for any of these companies
    users = frappe.db.sql("""
        SELECT DISTINCT up.user
        FROM `tabUser Permission` up
        WHERE up.allow = 'Company'
          AND up.for_value IN %(companies)s
          AND up.user LIKE %(txt)s
        LIMIT %(start)s, %(page_len)s
    """, {
        "companies": tuple(companies),
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })

    return users



@frappe.whitelist()
def get_users_by_company_permission(txt="", start=0, page_len=20):
    current_user = frappe.session.user

    # 1. Get companies for logged-in user
    companies = frappe.get_all(
        "User Permission",
        filters={
            "user": current_user,
            "allow": "Company"
        },
        pluck="for_value"
    )

    if not companies:
        return []

    # 2. Get users who share same company permissions, excluding self
    users = frappe.db.sql("""
        SELECT DISTINCT up.user
        FROM `tabUser Permission` up
        WHERE up.allow = 'Company'
          AND up.for_value IN %(companies)s
          AND up.user != %(current_user)s
          AND up.user LIKE %(txt)s
        ORDER BY up.user
        LIMIT %(start)s, %(page_len)s
    """, {
        "companies": tuple(companies),
        "current_user": current_user,
        "txt": f"%{txt}%",
        "start": int(start),
        "page_len": int(page_len)
    }, as_dict=True)

    return users


def _reverse_geocode(latitude, longitude):
	if latitude in (None, "") or longitude in (None, ""):
		return None

	try:
		lat = float(latitude)
		lng = float(longitude)
	except Exception:
		return None

	url = frappe.conf.get("nominatim_reverse_url", "https://nominatim.openstreetmap.org/reverse")
	params = {"format": "jsonv2", "lat": lat, "lon": lng}
	headers = {"User-Agent": f"{getattr(frappe.local, 'site', 'frappe')} User Live Location"}

	try:
		payload = make_get_request(url, params=params, headers=headers)
		payload = payload or {}
		return payload.get("display_name")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "User Live Location: Reverse geocode failed")
		return None
