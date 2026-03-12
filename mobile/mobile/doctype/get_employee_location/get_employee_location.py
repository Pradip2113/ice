# Copyright (c) 2026, Qunatbit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class GetEmployeeLocation(Document):
    pass
 
@frappe.whitelist()
def get_parameters(user, android_id, battery, latitude, longitude, timestamp):
    try:
        # If your DocType uses user as the document name (autoname = user)
        docname = user

        if frappe.db.exists("Get Employee Location", docname):
            doc = frappe.get_doc("Get Employee Location", docname)
        else:
            doc = frappe.new_doc("Get Employee Location")
            doc.name = docname   # IMPORTANT if autoname isn't enforcing it consistently
            doc.user = user

        doc.android_id = android_id
        doc.battery = int(battery)
        doc.latitude = float(latitude)
        doc.longitude = float(longitude)
        doc.date_time = timestamp

        doc.save(ignore_permissions=True)

        return {"status": "success"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Location Insert/Update Error")
        return {"status": "error", "message": str(e)}


# Hello from 192