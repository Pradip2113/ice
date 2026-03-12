import frappe
from datetime import datetime
from frappe import _
import requests
import json
from erpnext.accounts.utils import getdate
from mobile.mobile_env.app_utils import (
    gen_response,
    ess_validate,
    prepare_json_data,
    get_employee_by_user,
    exception_handel,
)
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
from mobile.mobile_env.location import add_user_location


@frappe.whitelist()
def get_customer_list():
    try:
        customer_list = frappe.get_list(
            "Customer",
            # filters={"custom_retailerdealer": "Dealer"},
            pluck="name",
        )
        return customer_list
    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist()
def get_customers_and_leads():
    """
    Returns a combined list of Customers and Leads with party_type, party (ID), and party_name.
    """
    try: 
        result = []

        # -------------------------------
        # Fetch Customers
        # -------------------------------
        customers = frappe.get_list(
            "Customer",
            fields=["name", "customer_name"]
        )
        for c in customers:
            result.append({
                "party_type": "Customer",
                "party": c.name,
                "party_name": c.customer_name
            })

        # -------------------------------
        # Fetch Leads
        # -------------------------------
        leads = frappe.get_list(
            "Lead",
            fields=["name", "company_name"]
        )
        for l in leads:
            result.append({
                "party_type": "Lead",
                "party": l.name,
                "party_name": l.company_name
            })

        return result

    except Exception as e:
        return exception_handel(e)
    
    
@frappe.whitelist()
def create_visit(**kwargs):
    try:
        data = kwargs
        emp_data = get_employee_by_user(frappe.session.user)

        if not emp_data:
            return gen_response(500, "Employee not found")

        # -------------------------
        # UPDATE EXISTING VISIT
        # -------------------------
        if data.get("name"):
            if not frappe.db.exists("Visit", data.get("name")):
                return gen_response(500, "Invalid Visit ID")

            visit_doc = frappe.get_doc("Visit", data.get("name"))

        # -------------------------
        # CREATE NEW VISIT
        # -------------------------
        else:
            visit_doc = frappe.new_doc("Visit")

        # -------------------------
        # COMMON FIELDS
        # -------------------------
        visit_in_address=get_address_from_lat_long(data.get("visit_in_latitude"),data.get("visit_in_longitude"))
        visit_out_address=get_address_from_lat_long(data.get("visit_out_latitude"),data.get("visit_out_longitude"))
        visit_doc.visit_to=data.get("visit_to")
        visit_doc.visitor=data.get("visitor")
        visit_doc.visitors_name=data.get("visitors_name")
        visit_doc.description = data.get("description")
        visit_doc.employee = emp_data.get("name")
        visit_doc.user = frappe.session.user

        # Visit IN fields
        visit_doc.visit_in_time = data.get("visit_in_time")
        visit_doc.visit_in_latitude = data.get("visit_in_latitude")
        visit_doc.visit_in_longitude = data.get("visit_in_longitude")
        visit_doc.visit_in_address = visit_in_address

        # Visit OUT fields
        visit_doc.visit_out_time = data.get("visit_out_time")
        visit_doc.visit_out_latitude = data.get("visit_out_latitude")
        visit_doc.visit_out_longitude = data.get("visit_out_longitude")
        visit_doc.visit_out_address = visit_out_address

        # Save / Insert
        if data.get("name"):
            visit_doc.save(ignore_permissions=True)
            msg = "Visit updated Successfully"
        else:
            visit_doc.insert(ignore_permissions=True)
            msg = "Visit created Successfully"

        if frappe.request.files.get("image"):
            file = frappe.request.files["image"]
            file_content = file.stream.read()

            # Correct way to save file in Frappe
            frappe.utils.file_manager.save_file(
                file.filename,
                file_content,
                visit_doc.doctype,
                visit_doc.name,
                decode=False,
                is_private=0,)
        # -------------------------
        # ADD USER LOCATION
        # -------------------------
        location_dict = {
            "lat": visit_doc.visit_out_latitude or visit_doc.visit_in_latitude,
            "lng": visit_doc.visit_out_longitude or visit_doc.visit_in_longitude,
            "reference_type": "Visit",
            "reference_name": visit_doc.name,
            "date": nowdate()
        }

        frappe.enqueue(
            "mobile.mobile_env.location.add_user_location",
            queue="short",
            timeout=60,
            **location_dict
        )

        return gen_response(200, msg)

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_visit_list(from_date=None, to_date=None):
    try:
        filters = {}

        # Add filters for from_date and to_date if provided
        if from_date and to_date:
            filters["date"] = ["between", [from_date, to_date]]
        elif from_date:
            filters["date"] = [">=", from_date]
        elif to_date:
            filters["date"] = ["<=", to_date]

        visits = frappe.get_list(
            "Visit",
            filters=filters,
            fields=[
                "name",
                "visitors_name",
                "date",
                "visit_in_time",
                "description",
                "visit_out_time",
                "visit_out_address",
                "creation","user"
            ],
            order_by="creation desc"        )

        for v in visits:
            in_time = v.get("visit_in_time")
            out_time = v.get("visit_out_time")

            # Calculate duration only if both times exist
            if in_time and out_time:
                duration_sec = frappe.utils.time_diff_in_seconds(out_time, in_time)
                v["duration"] = frappe.utils.flt(duration_sec / 60, 2)  # minutes
            else:
                v["duration"] = 0

        return gen_response(200, "Visit list fetched", visits)

    except Exception as e:
        return exception_handel(e)



import json
import frappe
from frappe.utils import getdate, pretty_date
from datetime import datetime

@frappe.whitelist()
def get_visit(visit_id):
    from frappe.utils import getdate, get_url
    from datetime import datetime
    import frappe

    try:
        # -------------------------
        # FETCH VISIT
        # -------------------------
        if not frappe.db.exists("Visit", visit_id):
            return gen_response(404, "Visit not found")

        visit = frappe.get_doc("Visit", visit_id)
        visit_data = visit.as_dict()

        # -------------------------
        # FORMAT DATE
        # -------------------------
        if visit_data.get("date"):
            visit_data["date"] = getdate(visit_data["date"]).strftime("%d-%m-%Y")

        # -------------------------
        # FORMAT TIME
        # -------------------------
        if visit_data.get("time"):
            try:
                visit_data["time"] = datetime.strptime(
                    str(visit_data["time"]).split(".")[0],
                    "%H:%M:%S"
                ).strftime("%I:%M %p")
            except Exception:
                pass  # prevent crash

        # -------------------------
        # FETCH LATEST ATTACHMENT
        # -------------------------
        file_url = frappe.db.get_value(
            "File",
            {
                "attached_to_doctype": "Visit",
                "attached_to_name": visit_id
            },
            "file_url",
            order_by="creation desc"
        )

        visit_data["attachment_url"] = (
            get_url(file_url) if file_url else None
        )

        # -------------------------
        # SUCCESS RESPONSE
        # -------------------------
        return gen_response(
            200,
            "Visit detail fetched successfully",
            visit_data
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_visit error")
        return exception_handel(e)


def get_visit_comments(visit):
    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_name": ["like", "%{0}%".format(visit.get("name"))],
            "comment_type": "Comment",
        },
        fields=[
            "content as comment",
            "comment_by",
            "reference_name",
            "creation",
            "comment_email",
        ],
    )
    
    for comment in comments:
        comment["commented"] = pretty_date(comment["creation"])
        # comment["creation"] = datetime.strptime(comment["creation"], "%Y-%m-%d %H:%M:%S.%f").strftime("%I:%M %p")
        
        user_image = frappe.get_value(
            "User", comment["comment_email"], "user_image", cache=True
        )
        comment["user_image"] = user_image

    return comments



def get_address_from_lat_long(latitude,longitude):
    if latitude and longitude:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json"
        }
        headers = {"User-Agent": "Frappe"}

        res = requests.get(url, params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            address = res.json().get("display_name", "")
            return address
    return ""