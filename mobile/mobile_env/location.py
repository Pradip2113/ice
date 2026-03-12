import frappe

from mobile.mobile_env.app_utils import (
    ess_validate,
    exception_handel,
    gen_response,
    get_employee_by_user,
)

"""save user location"""

"""{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [72.855663, 19.080709],
          [72.871113, 19.09531],
          [72.873344, 19.078438],
          [72.86459, 19.067731],
          [72.848454, 19.073084],
          [72.854633, 19.081521],
          [72.840214, 19.105204]
        ]
      }
    }
  ]
}
"""

@frappe.whitelist()
def user_location(**kwargs):
    try:
        # ───────────────────────────────────────── Validate Payload ─────────────────────────────────────────
        locations = kwargs.get("location")
        date = kwargs.get("date")

        if not locations or not isinstance(locations, list):
            return gen_response(400, "location must be a non-empty list")

        if not date:
            return gen_response(400, "date is required")

        # ───────────────────────────────────────── Get Employee ─────────────────────────────────────────
        user = frappe.session.user

        # ───────────────────────────────────────── Fetch or Create Doc ─────────────────────────────────────────
        # doc_name = frappe.db.get_value(
        #     "Employee Location",
        #     {"user": user, "date": date},
        #     "name",
        #     cache=True,
        # )

        # if doc_name:
        #     # Existing document → append locations
        #     location_doc = frappe.get_doc("Employee Location", doc_name)

        #     for loc in locations:
        #         location_doc.append("location_table", loc)

        #     location_doc.save(ignore_permissions=True)

        # else:
        #     # New document
        #     location_doc = frappe.get_doc({
        #         "doctype": "Employee Location",
        #         "user": user,
        #         "date": date,
        #         "location_table": locations,
        #     })
        #     location_doc.insert(ignore_permissions=True)

        return gen_response(200, "Location updated successfully")

    except Exception as e:
        frappe.log_error(
            title="Employee Location API Error",
            message=frappe.get_traceback(),
        )
        return exception_handel(e)
 
@frappe.whitelist()
def add_user_location(*args, **kwargs):
    try:
        # Extract fields
        lat = kwargs.get("lat")
        lng = kwargs.get("lng")
        reference_type = kwargs.get("reference_type")
        reference_name = kwargs.get("reference_name")
        date = kwargs.get("date")

        # -------------------------------------
        # Validation
        # -------------------------------------
        if not lat or not lng:
            return gen_response(500, "Latitude and Longitude are required.")

        if not date:
            return gen_response(500, "Date is required.")

        # The logged-in user
        user = frappe.session.user

        # -------------------------------------
        # Check if document already exists
        # -------------------------------------
        existing_doc = frappe.db.exists(
            "Employee Location",
            {"user": user, "date": date}
        )

        if not existing_doc:
            # Create new document
            doc = frappe.get_doc({
                "doctype": "Employee Location",
                "user": user,
                "date": date,
                "location_table": []
            })
        else:
            # Load existing doc
            doc = frappe.get_doc("Employee Location", existing_doc)

        # -------------------------------------
        # Add location entry to child table
        # -------------------------------------
        doc.append("location_table", {
            "latitude": lat,
            "longitude": lng,
            "reference_type": reference_type,
            "reference_name": reference_name,
            "datetime": frappe.utils.now_datetime()
        })

        # Save document
        doc.save(ignore_permissions=True)

        return gen_response(200, "Location added successfully.")

    except Exception as e:
        return exception_handel(e)

