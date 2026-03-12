import json
import os
import calendar
import frappe
from frappe import _
from hrms.hr.doctype.leave_application.leave_application import (
            get_leave_balance_on,
        )
from bs4 import BeautifulSoup
from frappe.utils import cstr, now, today
from frappe.auth import LoginManager
from frappe.permissions import has_permission
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
from frappe.defaults import get_user_default
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
from mobile.mobile_env.location import add_user_location
from datetime import datetime, timedelta
from erpnext.accounts.utils import get_fiscal_year


#done by shivraj
import frappe
from frappe.auth import LoginManager

@frappe.whitelist(allow_guest=True)
def login(usr, pwd, android_id=None):
    try:
        login_manager = LoginManager()
        login_manager.authenticate(usr, pwd)
        login_manager.post_login()

        message = frappe.response.get("message")

        if message != "Logged In":
            return gen_response(500, message or "Login failed")

        user = login_manager.user

        # Device binding only if android_id is provided
        if android_id:
            stored_id = frappe.db.get_value("User", user, "bio")

            # First login with device id
            if not stored_id:
                frappe.db.set_value("User", user, "bio", android_id, update_modified=False)

            # Restrict login from another device
            elif stored_id != android_id:
                frappe.throw("This account is restricted to another device.")

        frappe.response["user"] = user
        frappe.response["key_details"] = generate_key(user)

        return gen_response(200, "Logged In", {
            "user": frappe.response["user"],
            "key_details": frappe.response["key_details"],
        })

    except frappe.AuthenticationError:
        return gen_response(401, "Invalid username or password")

    except frappe.ValidationError as e:
        return gen_response(403, str(e))

    except Exception as e:
        return exception_handel(e)

def validate_employee(user):
    if not frappe.db.exists("Employee", dict(user_id=user)):
        frappe.response["message"] = "Please link Employee with this user"
        raise frappe.AuthenticationError(frappe.response["message"])


@frappe.whitelist()
def get_user_document():
    user_doc = frappe.get_doc("User", frappe.session.user)
    return user_doc

@frappe.whitelist()
def user_has_permission():
    permission_list=[]
    doclist=["Warehouse","Attendance Request","Project Lead","Stock Entry","Delivery Note","Employee Checkin","Sales Invoice","Sales Order","Lead","Quotation","Leave Application","Expense Claim","Attendance","Customer","Visit","Marketing Material Issue","Employee","Holiday List","Tours","Compensatory Leave Request"]
    for i in doclist:
        permission=has_permission(i)
        if permission:
            permission_list.append(i)
    return permission_list



from frappe.desk.query_report import run
@frappe.whitelist()
def get_item_warehouse_stock():
    try:
        # Get default company for mobile app
        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")

        # Fiscal year dates
        year = get_fiscal_year(nowdate(), company=company, as_dict=True)
        from_date = year.get("year_start_date")
        to_date = year.get("year_end_date")

        # Report filters
        filters = {
            "company": company,
            "from_date": from_date,
            "to_date": to_date,
            "include_uom": 1,
            "include_zero_stock_items": 1,
        }

        # Run Stock Balance report
        report_output = run(
            "Stock Balance",
            filters=filters,
            ignore_prepared_report=True,
            ignore_user_permissions=False
        )

        rows = report_output.get("result", [])

        # Enabled warehouses
        enabled_warehouses = frappe.get_list(
            "Warehouse",
            filters={"disabled": 0},
            pluck="name"
        )

        clean_items = []

        for row in rows:

            # Skip non-dict rows (like totals)
            if not isinstance(row, dict):
                continue

            if not row.get("item_code"):
                continue

            # ✅ SHOW ONLY ENABLED WAREHOUSES
            if row.get("warehouse") not in enabled_warehouses:
                continue

            clean_items.append({
                "item_code": row.get("item_code"),
                "item_name": row.get("item_name"),
                "warehouse": row.get("warehouse"),
                "actual_qty": float(row.get("bal_qty") or 0),
            })

        return gen_response(200, "Stocks fetched successfully", clean_items)

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def create_marketing_issue(data):
    try:
        data = frappe._dict(json.loads(data))

        doc = frappe.new_doc("Marketing Material Issue")
        doc.sales_person = data.sales_person
        doc.customer = data.customer
        doc.date = data.date
        doc.remarks = data.remarks

        for row in data.items:
            doc.append("items", {
                "item_code": row["item_code"],
                "item_name": row["item_name"],
                "qty_given": row["qty_given"],
                "uom": row["uom"],
            })

        doc.insert(ignore_permissions=True)
        return {"status": 200, "message": "Submitted", "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Marketing Issue Error")
        return {"status": 400, "message": str(e)}

# @frappe.whitelist()
# def get_item_warehouse_stock():
#     try:
#         # Get default company for mobile app
#         company = frappe.get_cached_value(
#             "Company",
#             {"custom_company_default_for_mobile_app": 1},
#             "name"
#         )
#         # Get enabled warehouses
#         enabled_warehouses = frappe.get_list(
#             "Warehouse",
#             filters={"disabled": 0},
#             pluck="name"
#         )

#         # Fetch stock from tabBin
#         bin_data = frappe.get_list(
#             "Bin",
#             filters={"warehouse": ["in", enabled_warehouses]},
#             fields=["item_code", "item_name", "warehouse", "actual_qty"]
#         )
#         clean_items = []

#         for row in bin_data:
#             if not isinstance(row, dict):
#                 continue
#             if not row.get("item_code"):
#                 continue
#             if row.get("warehouse") not in enabled_warehouses:
#                 continue

#             clean_items.append({
#                 "item_code": row.get("item_code"),
#                 "item_name": row.get("item_name"),
#                 "warehouse": row.get("warehouse"),
#                 "actual_qty": float(row.get("bal_qty") or 0),
#             })

#         return gen_response(200, "Stocks fetched successfully", clean_items)

#     except Exception as e:
#         return exception_handel(e)

@frappe.whitelist()
def create_tour(**kwargs):
    try:
        data = kwargs

        # ---------------------------------
        # Get logged-in employee
        # ---------------------------------
        emp_data = get_employee_by_user(
            frappe.session.user,
            fields=["name", "default_shift"]
        )
        if not emp_data:
            return gen_response(404, "Employee not found")

        # ---------------------------------
        # Validate required fields
        # ---------------------------------
        if not data.get("area"):
            frappe.throw("Area is required")

        if not data.get("date"):
            frappe.throw("Date is required")

        # ---------------------------------
        # Create Tour
        # ---------------------------------
        tour_doc = frappe.new_doc("Tours")
        tour_doc.area = data.get("area")
        tour_doc.date = data.get("date")
        tour_doc.total_calls = data.get("total_calls", 0)
        tour_doc.emplyoee = emp_data.get("name")
        tour_doc.description = data.get("description", "")

        tour_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            200,
            "Tour created successfully",
            {"tour_id": tour_doc.name}
        )

    except Exception as e:
        # ---------------------------------
        # ERROR LOGGING
        # ---------------------------------
        frappe.log_error(
            title="Create Tour API Error",
            message=frappe.get_traceback()
        )

        return exception_handel(e)




@frappe.whitelist()
def add_comment(reference_doctype=None, reference_name=None, content=None):
    try:
        from frappe.desk.form.utils import add_comment

        comment_by = frappe.db.get_value(
            "User", frappe.session.user, "full_name", as_dict=1
        )

        add_comment(
            reference_doctype=reference_doctype,
            reference_name=reference_name,
            content=content,
            comment_email=frappe.session.user,
            comment_by=comment_by.get("full_name"),
        )
        return gen_response(200, "Comment Added Successfully")

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_comments(reference_doctype=None, reference_name=None):
    """
    reference_doctype: doctype
    reference_name: docname
    """
    try:
        current_site=frappe.local.site
        filters = [
            ["Comment", "reference_doctype", "=", f"{reference_doctype}"],
            ["Comment", "reference_name", "=", f"{reference_name}"],
            ["Comment", "comment_type", "=", "Comment"],
        ]
        comments = frappe.get_all(
            "Comment",
            filters=filters,
            fields=[
                "content as comment",
                "comment_by",
                "creation",
                "comment_email",
            ],
        )

        for comment in comments:
            user_image = frappe.get_value(
                "User", comment.comment_email, "user_image", cache=True
            )
            
       
            if user_image is not None:
                comment["user_image"] = frappe.utils.get_url()+ user_image
            else:
                comment["user_image"] = None
            comment["commented"] = pretty_date(comment["creation"])
            comment["creation"] = comment["creation"].strftime('%Y-%m-%d %H:%M %p')

        return gen_response(200, "Comment Getting Successfully", comments)

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist()
def get_dashboard():
    try:
        from frappe.utils import today, nowdate
        from datetime import datetime

        # ---------------------------
        # Helper Functions
        # ---------------------------
        def safe_get_value(doctype, filters, fieldname):
            try:
                return frappe.get_value(doctype, filters, fieldname)
            except frappe.DoesNotExistError:
                return None

        def format_time(dt):
            return dt.strftime("%d-%b %I:%M%p") if dt else ""

        def format_short_time(dt):
            return dt.strftime("%I:%M%p") if dt else ""

        # def get_last_location(parent_name):
        #     if not parent_name:
        #         return {}
        #     loc = frappe.get_all(
        #         "employee location table",  # actual child table
        #         filters={"parent": parent_name},
        #         fields=["latitude", "longitude", "datetime"],
        #         order_by="datetime desc",
        #         limit_page_length=1
        #     )
        #     return loc[0] if loc else {"latitude": None, "longitude": None, "datetime": None}

        def get_user_image(user, is_employee, emp_name=None):
            try:
                if is_employee:
                    img = frappe.get_cached_value("Employee", emp_name, "image")
                else:
                    img = frappe.get_cached_value("User", user, "user_image")
                return frappe.utils.get_url(img) if img else None
            except:
                return None

        # ---------------------------
        # Employee / User
        # ---------------------------
        user = frappe.session.user
        emp_data = get_employee_by_user(user, fields=["name", "company", "employee_name"]) or None
        is_employee = bool(emp_data)
        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")
        if not is_employee:
            user_doc = frappe.get_doc("User", user)
            emp_data = {
                "name": None,
                "company": company or "Employee Dashboard",
                "employee_name": user_doc.full_name,
            }

        # ---------------------------
        # Attendance
        # ---------------------------
        start_today = f"{today()} 00:00:00"
        end_today = f"{today()} 23:59:59"

        if is_employee:
            filters_common = {"employee": emp_data.get("name"), "time": ["between", [start_today, end_today]]}
            in_time_val = frappe.db.get_value(
                "Employee Checkin",
                {**filters_common, "log_type": "IN"},
                "time",
                order_by="time asc",   # ✅ first IN
            )

            out_time_val = frappe.db.get_value(
                "Employee Checkin",
                {**filters_common, "log_type": "OUT"},
                "time",
                order_by="time desc",  # ✅ last OUT
            )

            log_details = get_last_log_details(emp_data.get("name")) or {}
            name=frappe.db.get_value("Employee Location",{"user":frappe.session.user,"date":today()})
            last_location = {"latitude": None, "longitude": None, "datetime": None}
        else:
            in_time_val = out_time_val = None
            log_details = {}
            last_location = {"latitude": None, "longitude": None, "datetime": None}

        # ---------------------------
        # Role
        # ---------------------------
        roles = frappe.get_roles(user)
        user_role = "user"
        if "Employee Tracker Manager" in roles:
            user_role = "manager"
        else:
            user_role = "employee"
        # ---------------------------
        # Monthly Summary
        # ---------------------------
        today_date = nowdate()
        year, month = today_date[:4], today_date[5:7]
        start_date = f"{year}-{month}-01"
        end_date = frappe.utils.get_last_day(start_date)

        monthly_summary = {
            "month": month,
            "year": year,
            "visit": {"total": frappe.db.count("Visit", {"owner": user, "creation": ["between", [start_date, end_date]]})},
            "attendance": {"total": frappe.db.count("Attendance", {"employee": emp_data.get("name") if is_employee else None, "status": "Present", "attendance_date": ["between", [start_date, end_date]]})},
            "leave": {"total": frappe.db.count("Leave Application", {"employee": emp_data.get("name") if is_employee else None, "from_date": ["between", [start_date, end_date]]})},
            "orders": {"total": frappe.db.count("Sales Order", {"owner": user, "transaction_date": ["between", [start_date, end_date]]})},
            "leads": {"total": frappe.db.count("Lead", {"owner": user, "creation": ["between", [start_date, end_date]]})},
            "tours": {"total": frappe.db.count("Tours", {"emplyoee": emp_data.get("name") if is_employee else None, "date": ["between", [start_date, end_date]]})}
            
        }

        # ---------------------------
        # Dashboard Data
        # ---------------------------
        dashboard_data = {
            "in_time": format_time(in_time_val),
            "out_time": format_time(out_time_val),
            "last_log_type": log_details.get("log_type", "") if is_employee else "",
            "last_log_time": format_short_time(log_details.get("time")) if log_details else "",
            "last_location": last_location,
            "sales_person": get_sales_person_dashboard() or [],
            "role": user_role,
            "tracking_enabled": bool(frappe.db.get_value("Employee", {"name": emp_data.get("name") if is_employee else None}, "custom_mobile_tracking")),
            "territorylist": frappe.get_list(
                "Territory",
                filters={"is_group": 0},
                pluck="name",
                order_by="name asc"  # ascending order
            ),
            "emp_name": emp_data.get("employee_name"),
            "email": user,
            "company": emp_data.get("company"),
            "employee_image": get_user_image(user, is_employee, emp_data.get("name")),
            "is_employee": is_employee,
            "monthly_summary": monthly_summary,
        }

        return gen_response(200, "Dashboard data fetched successfully", dashboard_data)

    except Exception as e:
        return exception_handel(e)




@frappe.whitelist()
def get_emp_name():
    try:
        emp_data = frappe.get_doc("User",frappe.session.user)
        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")
        dashboard_data = {
            "emp_name":emp_data.full_name,
            "email":emp_data.email,
            "company": company if company else None,
        }
        str1=frappe.get_cached_value(
            "User",frappe.session.user, "user_image",
        )
      
        if str1 is not None:
            dashboard_data["employee_image"] = frappe.utils.get_url()+ str1
        else:
            dashboard_data["employee_image"] = None
        return gen_response(200, "Dashboard data get successfully", dashboard_data)

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_last_log_details(employee):
    log_details = frappe.db.sql(
        """select log_type,time from `tabEmployee Checkin` where employee=%s and DATE(time)=%s order by time desc""",
        (employee, today()),
        as_dict=1,
    )

    if log_details:
        return log_details[0]
    else:
        return {"log_type": "OUT", "time": None}


@frappe.whitelist()
def change_password(**kwargs):
    try:
        from frappe.utils.password import check_password, update_password
        data=kwargs
        user = frappe.session.user
        current_password = data.get("current_password")
        new_password = data.get("new_password")
        check_password(user, current_password)
        update_password(user, new_password)
        return gen_response(200, "Password updated")
    except frappe.AuthenticationError:
        return gen_response(500, "Incorrect current password")
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_profile():
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        employee_details = frappe.get_cached_value(
            "Employee",
            emp_data.get("name"),
            [
                "employee",
                "employee_name",
                "company",
                "designation",
                "name",
                "date_of_joining",
                "date_of_birth",
                "gender",
                "company_email",
                "personal_email",
                "cell_number",
                "emergency_phone_number",
            ],
            as_dict=True,
        )
        employee_details["date_of_joining"] = employee_details[
            "date_of_joining"
        ].strftime("%d-%m-%Y")
        employee_details["date_of_birth"] = employee_details["date_of_birth"].strftime(
            "%d-%m-%Y"
        )
        image=frappe.get_cached_value(
            "Employee", emp_data.get("name"), "image"
        )
        if image is not None:
            employee_details["employee_image"] = frappe.utils.get_url()+ image
        else:
            employee_details["employee_image"] = None
    
        return gen_response(200, "My Profile", employee_details)
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def change_status(doc_name,type):
    try:
        frappe.db.set_value('Lead', doc_name, 'status', type, update_modified=True)
        return gen_response(200,'Status Changed')
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def add_note_in_lead(doc_name, note):
    try:
        doc=frappe.get_doc("Lead",{'name':doc_name},['notes'])
        doc.append("notes", {"note": note, "added_by": frappe.session.user, "added_on": now()})
        doc.save()
        return gen_response(200, "Note Added Successfully")
    
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def update_profile_picture():
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        from frappe.handler import upload_file

        employee_profile_picture = upload_file()
        employee_profile_picture.attached_to_doctype = "Employee"
        employee_profile_picture.attached_to_name = emp_data.get("name")
        employee_profile_picture.attached_to_field = "image"
        employee_profile_picture.save(ignore_permissions=True)

        frappe.db.set_value(
            "Employee", emp_data.get("name"), "image", employee_profile_picture.file_url
        )
        if employee_profile_picture:
            frappe.db.set_value(
                "User",
                frappe.session.user,
                "user_image",
                employee_profile_picture.file_url,
            )
        return gen_response(200, "Employee profile picture updated successfully")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def edit_note_in_lead(doc_name, note, row_id):
    doc=frappe.get_doc("Lead",{'name':doc_name},['notes'])
    for d in doc.notes:
        if cstr(d.name) == row_id:
            d.note = note
            d.db_update()

@frappe.whitelist()
def delete_note_in_lead(doc_name, row_id):
    try:
        doc=frappe.get_doc("Lead",{'name':doc_name},['notes'])
        for d in doc.notes:
            if cstr(d.name) == row_id:
                doc.remove(d)
                break
        doc.save()
        return gen_response(200, "Comment Delete Successfully")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_data_from_notes(doc_name):
    emp_data = get_employee_by_user(frappe.session.user, fields=["name", "company", "employee_name"])
    doc = frappe.get_doc("Lead", {'name': doc_name}, ['notes'])
    note_li = []
    current_site = frappe.local.site
   
   
    for i in doc.notes:
        note_dict = {}
        
        # Use BeautifulSoup to extract text from HTML string
        soup = BeautifulSoup(i.note, 'html.parser')

        # Find all <p> tags and extract the text
        paragraphs = soup.find_all('p')

        # Extracted text from <p> tags
        text_list = [p.get_text(strip=True) for p in paragraphs]

        # Remove empty strings from the list
        text_list = list(filter(None, text_list))
        
        # Add formatted message to the note_dict
        note_dict["name"] = int(i.name)
        note_dict["note"] = str(i.note)
        note_dict["commented"] = str(i.added_by)
        
        # Check if added_on is not None before formatting
        note_dict["added_on"] = pretty_date(i.creation)
        str1 = frappe.get_value(
                "User", i.added_by, "user_image", cache=True
            )
        frappe.msgprint(str1)
        if str1 is not None:
            note_dict['image'] = frappe.utils.get_url()+ str1
        else:
            note_dict['image'] = None
        
        note_li.append(note_dict)

    return gen_response(200, "Notes get successfully", note_li)


@frappe.whitelist()
def create_employee_log(log_type, latitude=None, longitude=None, meter_reading=None):
    try:
        # Get employee linked to logged in user
        emp_data = get_employee_by_user(
            frappe.session.user,
            fields=["name", "default_shift"]
        )

        employee = emp_data.get("name")
        if not employee:
            return gen_response(500, "Employee not found.")

        # Create check-in document
        log_doc = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": employee,
            "log_type": log_type,
            "time": now_datetime(),
            "device_id": f"{latitude},{longitude}",
            "latitude": latitude,
            "longitude": longitude,
            "custom_meter_reading": meter_reading,
        }).insert(ignore_permissions=True)

        # -------------------------
        # Handle Photo Upload
        # -------------------------
        if frappe.request.files.get("photo"):
            file = frappe.request.files["photo"]
            file_content = file.stream.read()

            # Correct way to save file in Frappe
            frappe.utils.file_manager.save_file(
                file.filename,
                file_content,
                "Employee Checkin",
                log_doc.name,
                decode=False,
                is_private=0,)

        # Update last sync
        update_shift_last_sync(emp_data)

        # -------------------------
        # Add Location Entry
        # -------------------------
        if log_type =="IN" and (latitude or longitude):
            location_dict = {
                "lat": latitude if latitude else None,
                "lng": longitude if longitude else None,
                "reference_type": "Employee Checkin",
                "reference_name": log_doc.name,
                "date": nowdate()
            }
            add_user_location(**location_dict)
        return gen_response(200, "Employee Log Added")

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_monthly_summary():
    try:
        user = frappe.session.user
        emp = get_employee_by_user(user)

        if not emp:
            return gen_response(404, "Employee not found")

        # ---------------- CURRENT MONTH ----------------
        today = nowdate()  # YYYY-MM-DD
        year = today[:4]
        month = today[5:7]

        start_date = f"{year}-{month}-01"
        end_date = frappe.utils.get_last_day(start_date)

        # ---------------- VISITS ----------------
        visit_count = frappe.db.count(
            "Visit",
            {
                "employee": emp["name"],
                "creation": ["between", [start_date, end_date]]
            }
        )

        # ---------------- ATTENDANCE ----------------
        present = frappe.db.count(
            "Attendance",
            {
                "employee": emp["name"],
                "status": "Present",
                "attendance_date": ["between", [start_date, end_date]]
            }
        )

        absent = frappe.db.count(
            "Attendance",
            {
                "employee": emp["name"],
                "status": "Absent",
                "attendance_date": ["between", [start_date, end_date]]
            }
        )

        # ---------------- LEAVE ----------------
        leave_applied = frappe.db.count(
            "Leave Application",
            {
                "employee": emp["name"],
                "from_date": ["between", [start_date, end_date]]
            }
        )

        leave_approved = frappe.db.count(
            "Leave Application",
            {
                "employee": emp["name"],
                "status": "Approved",
                "from_date": ["between", [start_date, end_date]]
            }
        )

        # ---------------- ORDERS ----------------
        orders = frappe.db.get_all(
            "Sales Order",
            filters={
                "owner": user,
                "transaction_date": ["between", [start_date, end_date]]
            },
            fields=["rounded_total"]
        )

        total_orders = len(orders)
        total_amount = sum(o.rounded_total for o in orders if o.rounded_total)

        # ---------------- LEADS ----------------
        leads_total = frappe.db.count(
            "Lead",
            {
                "owner": user,
                "creation": ["between", [start_date, end_date]]
            }
        )

        return gen_response(200, "Current Month Summary", {
            "month": month,
            "year": year,
            "visit": {"total": visit_count},
            "attendance": {
                "present": present,
                "absent": absent
            },
            "leave": {
                "applied": leave_applied,
                "approved": leave_approved
            },
            "orders": {
                "count": total_orders,
                "amount": total_amount
            },
            "leads": {
                "total": leads_total
            }
        })

    except Exception as e:
        return exception_handel(e)



def update_shift_last_sync(emp_data):
    if emp_data.get("default_shift"):
        frappe.db.set_value(
            "Shift Type",
            emp_data.get("default_shift"),
            "last_sync_of_checkin",
            now_datetime(),
        )


import frappe
from frappe.utils import nowdate
from frappe.utils.data import getdate
from frappe.utils import strip_html

@frappe.whitelist()
def get_holiday_list(year):
    try:
        if not year:
            return gen_response(500, "year is required")

        emp_data = get_employee_by_user(frappe.session.user)
        if not emp_data:
            return gen_response(500, "Employee not found")

        from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

        holiday_list_name = get_holiday_list_for_employee(
            emp_data.name, raise_exception=False
        )

        if not holiday_list_name:
            return gen_response(200, "Holiday list get successfully", [])

        holidays = frappe.get_all(
            "Holiday",
            filters={
                "parent": holiday_list_name,
                "holiday_date": ("between", [f"{year}-01-01", f"{year}-12-31"]),
            },
            fields=["description", "holiday_date"],
            order_by="holiday_date asc",
        )

        if not holidays:
            return gen_response(200, f"No holidays found for year {year}", [])

        out = []
        for h in holidays:
            d = getdate(h.holiday_date)

            # ✅ skip Sundays
            if d.weekday() == 6:
                continue

            out.append(
                {
                    "year": d.strftime("%Y"),
                    "date": d.strftime("%d %b"),
                    "day": d.strftime("%A"),
                    # ✅ remove html like <div><p>...</p></div>
                    "description": strip_html(h.description or "").strip(),
                }
            )

        return gen_response(200, "Holiday List", out)

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_leave_balance_dashboard():
    try:
        emp_data = get_employee_by_user(frappe.session.user, fields=["name", "company"])
        fiscal_year = get_fiscal_year(nowdate())[0]
        dashboard_data = {"leave_balance": []}
        if fiscal_year:
            res = get_leave_balance_report(
                emp_data.get("name"), emp_data.get("company"), fiscal_year
            )
            dashboard_data["leave_balance"] = res["result"]
        return gen_response(200, "Leave Balance data get successfully") , res["result"]
    except Exception as e:
        return exception_handel(e)




# def get_last_log_type(dashboard_data, employee):
#     logs = frappe.get_all(
#         "Employee Checkin",
#         filters={"employee": employee},
#         fields=["log_type"],
#         order_by="time desc",
#     )

#     if len(logs) >= 1:
#         dashboard_data["last_log_type"] = logs[0].log_type



@frappe.whitelist()
def make_leave_application(**kwargs):
    try:
        from hrms.hr.doctype.leave_application.leave_application import (
            get_leave_approver,
        )

        emp_data = get_employee_by_user(frappe.session.user)
        if not len(emp_data) >= 1:
            return gen_response(500, "Employee does not exists")
        validate_employee_data(emp_data)
        leave_application_doc = frappe.get_doc(
            dict(
                doctype="Leave Application",
                employee=emp_data.get("name"),
                company=emp_data.company,
                leave_approver=get_leave_approver(emp_data.name),
            )
        )
        leave_application_doc.update(kwargs)
        res = leave_application_doc.insert()
        gen_response(200, "Leave Application Successfully Added",res)
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_leave_type(from_date=None, to_date=None):
    from frappe.utils import today
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        leave_types = frappe.get_all(
            "Leave Type", filters={}, fields=["name", "'0' as balance"]
        )
        from_date=today()
        for leave_type in leave_types:
            leave_type["balance"] = get_leave_balance_on(
                emp_data.get("name"),
                leave_type.get("name"),
                from_date,
                consider_all_leaves_in_the_allocation_period=True,
            )
        return gen_response(200, "Leave Type Get Successfully", leave_types)
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_leave_application(name):
    """
    Get Leave Application which is already applied. Get Leave Balance Report
    """
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        validate_employee_data(emp_data)

        if not frappe.db.exists(
            "Leave Application", {"name": name, "employee": emp_data.get("name")}
        ):
            return gen_response(500, "Leave application does not exists!")

        leave_application_fields = [
            "name",
            "leave_type",
            "total_leave_days",
            "description",
            "status",
            "half_day",
            "from_date",
            "to_date",
            "posting_date",
            "docstatus",
            "half_day_date",
        ]

        leave_application = frappe.db.get_value(
            "Leave Application", name, leave_application_fields, as_dict=True
        )

        return gen_response(200, "Leave data getting successfully", leave_application)
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def delete_leave_application(name):
    try:
        emp = get_employee_by_user(frappe.session.user)
        validate_employee_data(emp)

        if not frappe.db.exists(
            "Leave Application",
            {"name": name, "employee": emp.get("name")}
        ):
            frappe.throw("Leave application not found", frappe.PermissionError)

        doc = frappe.get_doc("Leave Application", name)

        if doc.docstatus == 1:
            frappe.throw("Submitted leave cannot be deleted")

        doc.delete()

        return gen_response(200, "Leave deleted successfully")

    except Exception as e:
        return exception_handel(e)




@frappe.whitelist()
def make_compoff_application(**kwargs):
    try:

        emp_data = get_employee_by_user(frappe.session.user)
        if not len(emp_data) >= 1:
            return gen_response(500, "Employee does not exists")
        validate_employee_data(emp_data)
        leave_application_doc = frappe.get_doc(
            dict(
                doctype="Compensatory Leave Request",
                employee=emp_data.get("name"))
        )
        leave_application_doc.update(kwargs)
        res = leave_application_doc.insert()
        gen_response(200, "Compensatory Leave Request Successfully Added",res)
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_compoffleave_type(from_date=None, to_date=None):
    from frappe.utils import today
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        leave_types = frappe.get_all(
            "Leave Type", filters={"is_compensatory": 1}, fields=["name", "'0' as balance"]
        )
        from_date=today()
        for leave_type in leave_types:
            leave_type["balance"] = get_leave_balance_on(
                emp_data.get("name"),
                leave_type.get("name"),
                from_date,
                consider_all_leaves_in_the_allocation_period=True,
            )
        return gen_response(200, "Leave Type Get Successfully", leave_types)
    except Exception as e:
        return exception_handel(e)



@frappe.whitelist()
def get_compoff_request_list(**data):
    try:
        employee = frappe.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        )
        if not employee:
            return gen_response(500, "Employee record not found.")

        filters = [["Compensatory Leave Request", "employee", "=", employee]]
        if data.get("filters"):
            filters.extend(data.get("filters"))

        attendance_request_list = frappe.get_all(
            "Compensatory Leave Request",
            filters=filters,
            fields=[
                 "name",
            "leave_type",
            "reason",
            "half_day",
            "work_from_date",
            "work_end_date",
            "docstatus",
            "half_day_date",
            ],
        )

        for request in attendance_request_list:
            if request.get("from_date"):
                request["from_date"] = getdate(request["from_date"]).strftime(
                    "%d-%m-%Y"
                )
            if request.get("to_date"):
                request["to_date"] = getdate(request["to_date"]).strftime("%d-%m-%Y")

        return gen_response(
            200,
            "Compensatory Leave Request list retrieved successfully.",
            attendance_request_list,
        )
    except frappe.PermissionError as e:
        return gen_response(500, str(e))
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_compoff_application(name):
    """
    Get Compensatory Leave Request which is already applied.
    """
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        validate_employee_data(emp_data)

        if not frappe.db.exists(
            "Compensatory Leave Request", {"name": name, "employee": emp_data.get("name")}
        ):
            return gen_response(500, "Compensatory Leave Request does not exists!")

        leave_application_fields = [
            "name",
            "leave_type",
            "reason",
            "half_day",
            "work_from_date",
            "work_end_date",
            "docstatus",
            "half_day_date",
        ]

        leave_application = frappe.db.get_value(
            "Compensatory Leave Request", name, leave_application_fields, as_dict=True
        )

        return gen_response(200, "Leave data getting successfully", leave_application)
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def delete_compoff_application(name):
    try:
        emp = get_employee_by_user(frappe.session.user)
        validate_employee_data(emp)

        if not frappe.db.exists(
            "Compensatory Leave Request",
            {"name": name, "employee": emp.get("name")}
        ):
            frappe.throw("Compensatory Leave Request not found", frappe.PermissionError)

        doc = frappe.get_doc("Compensatory Leave Request", name)

        if doc.docstatus == 1:
            frappe.throw("Submitted leave cannot be deleted")

        doc.delete()

        return gen_response(200, "Compensatory Leave Request deleted successfully")

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def update_compoff_application(*args, **kwargs):
    try:
        emp_data = get_employee_by_user(frappe.session.user, fields=["name", "company"])
        if not len(emp_data) >= 1:
            return gen_response(500, "Employee does not exists!")
        validate_employee_data(emp_data)

        leave_id = kwargs.get("name")
        if not leave_id:
            return gen_response(500, "comp off ID is required!")

        if not frappe.db.exists("Compensatory Leave Request", kwargs.get("name")):
            return gen_response(500, "Compensatory Leave Request does not exists!")

        leave_application_doc = frappe.get_doc("Compensatory Leave Request", leave_id)
        leave_application_doc.update(kwargs)
        leave_application_doc.save()
        gen_response(200, "Compensatory Leave Request successfully updated!")
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def delete_expense_application(name):
    try:
        emp = get_employee_by_user(frappe.session.user)
        validate_employee_data(emp)

        if not frappe.db.exists(
            "Expense Claim",
            {"name": name, "employee": emp.get("name")}
        ):
            frappe.throw("Expense application not found", frappe.PermissionError)
        doc = frappe.get_doc("Expense Claim", name)

        if doc.docstatus == 1:
            frappe.throw("Submitted expense cannot be deleted")

        doc.delete()

        return gen_response(200, "Expense deleted successfully")
    except Exception as e:
        return exception_handel(e)



@frappe.whitelist()
def get_expense_list(month=None, year=None):
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        if not len(emp_data) >= 1:
            return gen_response(500, "Employee does not exist")
        validate_employee_data(emp_data)

        filters = {"employee": emp_data.get("name")}

        # Add filters for month and year if provided
        if month and year:
            start_date = frappe.utils.getdate(f"{year}-{month}-01")
            end_date = frappe.utils.get_last_day(start_date)
            filters["posting_date"] = ["between", [start_date, end_date]]

        expense_list = frappe.get_all(
            "Expense Claim",
            filters=filters,
            fields=["*"],
        )

        expense_data = []
        for expense in expense_list:
            (
                expense["expense_type"],
                expense["expense_description"],
                expense["expense_date"],
            ) = frappe.get_value(
                "Expense Claim Detail",
                {"parent": expense.name},
                ["expense_type", "description", "expense_date"],
            )
            expense["expense_date"] = expense["expense_date"].strftime("%d-%m-%Y")
            expense["posting_date"] = expense["posting_date"].strftime("%d-%m-%Y")
            expense["attachments"] = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Expense Claim",
                    "attached_to_name": expense.name,
                    "is_folder": 0,
                },
                fields=["file_url"],
            )
            expense["name"] = expense.name
            expense_data.append(expense)

        return gen_response(200, "Expense Date Get Successfully", expense_data)

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_attendance_list(year=None, month=None):
    try:
        if not year or not month:
            return gen_response(500, "year and month is required", [])
        emp_data = get_employee_by_user(frappe.session.user)
        present_count = 0
        absent_count = 0
        late_count = 0
        halfday_count=0
        onleave_count=0
        

        employee_attendance_list = frappe.get_all(
            "Attendance",
            filters={
                "employee": emp_data.get("name"),
                "attendance_date": [
                    "between",
                    [
                        f"{int(year)}-{int(month)}-01",
                        f"{int(year)}-{int(month)}-{calendar.monthrange(int(year), int(month))[1]}",
                    ],
                ],
            },
            fields=[
                "name",
                "attendance_date",
                "status",
                "working_hours",
                "time_format(in_time, '%h:%i%p') as in_time",
                "time_format(out_time, '%h:%i%p') as out_time",
                "late_entry",
            ],
        )

        if not employee_attendance_list:
            return gen_response(500, "No attendance found for this year and month", [])

        for attendance in employee_attendance_list:
            employee_checkin_details = frappe.get_all(
                "Employee Checkin",
                filters={"attendance": attendance.get("name")},
                fields=["log_type", "time_format(time, '%h:%i%p') as time"],
            )

            attendance["employee_checkin_detail"] = employee_checkin_details

            if attendance["status"] == "Present":
                present_count += 1

                if attendance["late_entry"] == 1:
                    late_count += 1

            elif attendance["status"] == "Absent":
                absent_count += 1
            
            elif attendance["status"] == "Half Day":
                halfday_count += 1
            
            elif attendance["status"] == "On Leave":
                onleave_count += 1

            del attendance["name"]
            # del attendance["status"]
            del attendance["late_entry"]

        attendance_details = {
            "days_in_month": calendar.monthrange(int(year), int(month))[1],
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "half day":halfday_count,
            "on leave":onleave_count
        }
        attendance_data = {
            "attendance_details": attendance_details,
            "attendance_list": employee_attendance_list,
        }
        return gen_response(
            200, "Attendance data getting Successfully", attendance_data
        )

    except Exception as e:
        return exception_handel(e)

def remove_duplicates(input_list, key_extractor):
    unique_keys = set()
    unique_list = []

    for item in input_list:
        key = key_extractor(item)
        if key not in unique_keys:
            unique_keys.add(key)
            unique_list.append(item)

    return unique_list

@frappe.whitelist()
def filter_customer_list():
    try:
        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")
        list = frappe.get_list(
            "Lead",
                fields=[
                    "company_name"
                ],
                filters={"company": company},
            )
        list=remove_duplicates(list,lambda item: item['company_name'])
        gen_response(200,"List get successfully", list)
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_travel_expense_data(expense_type=None, expense_date=None):
    """
    Returns km, rate per km and calculated amount for Bike/Car expenses
    """
    try:
        emp_data = get_employee_by_user(
            frappe.session.user, fields=["name", "company", "expense_approver"]
        )
        if not emp_data:
            return gen_response(500, "Employee not found")  

        if not expense_type or not expense_date:
            return gen_response(400, "Expense Type and Date are required")

        # ---------------- Get Rate per KM ----------------
        rate_per_km = frappe.db.get_value("Expense Claim Type", expense_type, "custom_per_km_rate")
        if rate_per_km is None:
            return gen_response(404, f"Rate per KM not found for {expense_type}", {})

        # ---------------- Get Employee Travel KM ----------------
        # Assume you have a DocType "Employee Location" with fields: employee, travel_date, km
        km = frappe.db.get_value(
            "Employee Location",
            {"user": frappe.session.user, "date": expense_date},
            "distance"
        ) or 0

        amount = km * rate_per_km

        data = {
            "km": km,
            "rate_per_km": rate_per_km,
            "amount": amount
        }

        return gen_response(200, "expense successfully", data)

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_expense(name):
    try:
        # Validate the input
        if not name:
            return gen_response(400, "Expense ID is required")

        # Get logged-in employee
        emp_data = get_employee_by_user(
            frappe.session.user, fields=["name", "company", "expense_approver"]
        )
        if not emp_data:
            return gen_response(500, "Employee does not exist")

        validate_employee_data(emp_data)

        # Check if the Expense Claim exists
        if not frappe.db.exists("Expense Claim", {"name": name}):
            return gen_response(404, f"Expense Claim {name} not found")

        # Fetch Expense Claim
        expense = frappe.get_doc("Expense Claim", name)

        # Fetch first expense detail (if exists)
        detail = frappe.db.get_value(
            "Expense Claim Detail",
            {"parent": expense.name},
            ["expense_type", "description", "expense_date", "amount","custom_rate","custom_km"],
            as_dict=True,
        )

        # Prepare the response in Flutter-friendly format
        expense_json = {
            "name": expense.name,
            "expense_type": detail.expense_type if detail else None,
            "expense_description": detail.description if detail else None,
            "docstatus": expense.docstatus,
            "expense_date": detail.expense_date if detail and detail.expense_date else None,
            "amount": float(detail.amount) if detail and detail.amount else 0.0,
            "custom_rate": float(detail.custom_rate) if detail and detail.custom_rate else 0.0,
            "custom_km": float(detail.custom_km) if detail and detail.custom_km else 0.0,
            "attachments": frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Expense Claim",
                    "attached_to_name": expense.name,
                    "is_folder": 0,
                },
                fields=["name", "file_name", "file_url"],
            ),
        }

        return gen_response(200, "Expense fetched successfully", expense_json)

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def apply_expense():
    try:
        emp_data = get_employee_by_user(
            frappe.session.user, fields=["name", "company", "expense_approver"]
        )

        if not len(emp_data) >= 1:
            return gen_response(500, "Employee does not exists")
        validate_employee_data(emp_data)

        payable_account = get_payable_account(emp_data.get("company"))
        expense_doc = frappe.get_doc(
            dict(
                doctype="Expense Claim",
                employee=emp_data.name,
                expense_approver=emp_data.expense_approver,
                expenses=[
                    {
                        "expense_date": frappe.form_dict.expense_date,
                        "expense_type": frappe.form_dict.expense_type,
                        "description": frappe.form_dict.description,
                        "amount": frappe.form_dict.amount,
                    }
                ],
                posting_date=today(),
                company=emp_data.get("company"),
                payable_account=payable_account,
            )
        ).insert()

        from frappe.handler import upload_file

        if "file" in frappe.request.files:
            file = upload_file()
            file.attached_to_doctype = "Expense Claim"
            file.attached_to_name = expense_doc.name
            file.save(ignore_permissions=True)

        return gen_response(200, "Expense applied Successfully", frappe.request.files)
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_leave_application_list():
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        
        leave_application_fields = [
            "name",
            "leave_type",
            "DATE_FORMAT(from_date, '%d-%m-%Y') as from_date",
            "DATE_FORMAT(to_date, '%d-%m-%Y') as to_date",
            "description",
            "status",
            "docstatus",
            "half_day",
            "half_day_date",
            "posting_date",
        ]
        upcoming_leaves = frappe.get_list(
            "Leave Application",
            filters={"from_date": [">", today()], "employee": emp_data.get("name")},
            fields=leave_application_fields,
        )

        taken_leaves = frappe.get_list(
            "Leave Application",
            fields=leave_application_fields,
            filters={"from_date": ["<=", today()], "employee": emp_data.get("name")},
        )
        fiscal_year = get_fiscal_year(nowdate())[0]
        if not fiscal_year:
            return gen_response(500, "Fiscal year not set")
        res = get_leave_balance_report(
            emp_data.get("name"), emp_data.get("company"), fiscal_year
        )
        leave_applications = {
            "upcoming": upcoming_leaves,
            "taken": taken_leaves,
            "balance": res["result"]        
            }
        return gen_response(200, "leave data getting successfully", leave_applications)
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_leave_balance_report(employee, company, fiscal_year):
    fiscal_year = get_fiscal_year(fiscal_year=fiscal_year, as_dict=True)
    year_start_date = get_date_str(fiscal_year.get("year_start_date"))
    year_end_date = get_date_str(fiscal_year.get("year_end_date"))
    filters_leave_balance = {
        "from_date": year_start_date,
        "to_date": year_end_date,
        "company": company,
        "employee": employee,
    }
    from frappe.desk.query_report import run

    return run("Employee Leave Balance", filters=filters_leave_balance)


@frappe.whitelist()
def target_variance_report():
    try:
        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")
        fiscal_year = get_fiscal_year(nowdate())[0]
        filters = {
            "company": company,
            "fiscal_year": fiscal_year,
            "doctype": "Sales Invoice",
            "period": "Yearly",
            "target_on": "Amount",
        }
        from frappe.desk.query_report import run

        attendance_report = run("Sales Person Target Variance Based On Item Group", filters=filters)

        # Ensure result is always defined
        result = attendance_report.get("result") if attendance_report.get("result") else []

        return gen_response(200, "Target Variance Report", result)
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def transaction_report():
    try:
        global_defaults = get_global_defaults() 
        company = global_defaults.get("default_company")        
        fiscal_year = get_fiscal_year(nowdate(), company=company, as_dict=True)
        frappe.msgprint(str(fiscal_year))
        year_start_date = get_date_str(fiscal_year.get("year_start_date"))
        year_end_date = get_date_str(fiscal_year.get("year_end_date"))
        filters = {
            "doc_type": "Sales Order",
            "from_date": year_start_date,
            "to_date": year_end_date,
            "company": company
        }
        from frappe.desk.query_report import run

        transaction_report = run("Sales Person-wise Transaction Summary", filters=filters)        
        # Ensure result is always defined and remove last two rows
        result = transaction_report.get("result") or []
        trimmed_result = result[:-2] if len(result) > 2 else []

        return gen_response(200, "Transaction Report", trimmed_result)

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist()
def sales_person_commission_report():
    try:
        global_defaults = get_global_defaults()     
        company = global_defaults.get("default_company")
        fiscal_year = get_fiscal_year(nowdate(),company=company,as_dict=True)
        year_start_date = get_date_str(fiscal_year.get("year_start_date"))  
        year_end_date = get_date_str(fiscal_year.get("year_end_date"))
        filters = {
            "doc_type": "Sales Order",
            "from_date": year_start_date,
            "to_date": year_end_date,
            "company": company,
        }
        from frappe.desk.query_report import run
        commission_report = run("Sales Person Commission Summary", filters=filters)
        # Ensure result is always defined
        result = commission_report.get("result") or []
        trimmed_result = result[:-2] if len(result) > 2 else []

        return gen_response(200, "Sales Person Commission Report", trimmed_result)
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def book_expense(**kwargs):
    try:
        emp_data = get_employee_by_user(
            frappe.session.user,
            fields=["name", "company", "expense_approver"]
        )

        if not emp_data:
            return gen_response(500, "Employee does not exist")

        validate_employee_data(emp_data)
        data = kwargs

        expense_id = data.get("name")
        amount = flt(data.get("amount") or 0)
        rate=flt(data.get("custom_rate") or 0)
        km=flt(data.get("custom_km") or 0)
        # -------------------------------
        # ADD OR UPDATE
        # -------------------------------
        if expense_id:
            # ---------- UPDATE ----------
            if not frappe.db.exists("Expense Claim", expense_id):
                return gen_response(404, "Expense Claim not found")

            expense_doc = frappe.get_doc("Expense Claim", expense_id)

            # allow update only in Draft
            if expense_doc.docstatus != 0:
                return gen_response(403, "Only draft expenses can be updated")

            row = expense_doc.expenses[0]

            row.expense_date = data.get("expense_date")
            row.expense_type = data.get("expense_type")
            row.description = data.get("expense_description")
            row.amount = amount
            row.sanctioned_amount = amount
            row.custom_rate=rate
            row.custom_km=km
            expense_doc.grand_total = amount
            expense_doc.save(ignore_permissions=True)

            action = "updated"

        else:
            # ---------- ADD ----------
            payable_account = get_payable_account(emp_data.company)

            expense_doc = frappe.get_doc({
                "doctype": "Expense Claim",
                "employee": emp_data.name,
                "expense_approver": emp_data.expense_approver,
                "posting_date": today(),
                "company": emp_data.company,
                "payable_account": payable_account,
                "expenses": [{
                    "expense_date": data.get("expense_date"),
                    "expense_type": data.get("expense_type"),
                    "description": data.get("expense_description"),
                    "amount": amount,
                    "sanctioned_amount": amount,
                    "custom_rate":rate,
                    "custom_km":km,
                }],
                "grand_total": amount,
            }).insert(ignore_permissions=True)

            action = "created"

        # -------------------------------
        # Attachments (common)
        # -------------------------------
        if data.get("attachments"):
            for file in data.get("attachments"):
                frappe.db.set_value(
                    "File",
                    file.get("name"),
                    {
                        "attached_to_doctype": "Expense Claim",
                        "attached_to_name": expense_doc.name,
                    }
                )

        return gen_response(
            200,
            f"Expense {action} successfully",
            expense_doc.name
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Book Expense Error")
        return exception_handel(e)


@frappe.whitelist()
def update_leave_application(*args, **kwargs):
    try:
        emp_data = get_employee_by_user(frappe.session.user, fields=["name", "company"])
        if not len(emp_data) >= 1:
            return gen_response(500, "Employee does not exists!")
        validate_employee_data(emp_data)

        leave_id = kwargs.get("name")
        if not leave_id:
            return gen_response(500, "Leave ID is required!")

        if not frappe.db.exists("Leave Application", kwargs.get("name")):
            return gen_response(500, "Leave application does not exists!")

        leave_application_doc = frappe.get_doc("Leave Application", leave_id)
        leave_application_doc.update(kwargs)
        leave_application_doc.save()
        gen_response(200, "Leave application successfully updated!")
    except Exception as e:
        return exception_handel(e)



# @frappe.whitelist()
def get_payable_account(company):
    try:
        default_payable_account = frappe.db.get_value(
                "Company", company, "default_payable_account"
            )
        return default_payable_account
    except Exception as e:
           return exception_handel(e)


@frappe.whitelist()
def get_attendance_details_dashboard():
    try:
        emp_data = get_employee_by_user(frappe.session.user, fields=["name", "company"])
        attendance_details = get_attendance_details(emp_data)
        return gen_response(
            200, "Attendance data get successfully", attendance_details
        )
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_sales_person_dashboard():
    try:
        from frappe.utils import get_first_day, get_last_day, nowdate

        emp_data = get_employee_by_user(
            frappe.session.user,
            fields=["name", "company", "expense_approver"]
        )

        today = nowdate()

        filters = {
            "from_date": get_first_day(today),
            "to_date": get_last_day(today),
            "employee": emp_data.get("name")
        }

        from frappe.desk.query_report import run

        report = run(
            "Visit and Tour Count",
            filters=filters,
            ignore_prepared_report=True
        )

        result = report.get("result") or []

        # ----------------------------------
        # CLEAN EMPTY + TOTAL ROWS
        # ----------------------------------
        cleaned_result = []
        for row in result:
            if isinstance(row, list):
                continue
            if not row.get("employee") or not row.get("date"):
                continue
            cleaned_result.append(row)

        return cleaned_result

    except Exception as e:
        return exception_handel(e)



def get_attendance_details(emp_data):
    last_date = get_last_day(today())
    first_date = get_first_day(today())
    total_days = date_diff(last_date, first_date)
    till_date_days = date_diff(today(), first_date)
    days_off = 0
    absent = 0
    total_present = 0
    attendance_report = run_attendance_report(
        emp_data.get("name"), emp_data.get("company")
    )
    if attendance_report:
        days_off = flt(attendance_report.get("total_leaves")) + flt(
            attendance_report.get("total_holidays")
        )
        absent = till_date_days - (
            flt(days_off) + flt(attendance_report.get("total_present"))
        )
        total_present = attendance_report.get("total_present")
    attendance_details = {
        "month_title": f"{frappe.utils.getdate().strftime('%B')} Details",
        "till_days":till_date_days,
        "total_days":total_days,
        "day off":float(days_off),
        "present":float(total_present),
        "absent":abs(float(absent))
        # "data": [
        #     {
        #         "type": "Total Days",
        #         "data": [
        #             till_date_days,
        #             total_days,
        #         ],
        #     },
        #     {
        #         "type": "Presents",
        #         "data": [
        #             total_present,
        #             till_date_days,
        #         ],
        #     },
        #     {
        #         "type": "Absents",
        #         "data": [
        #             absent,
        #             till_date_days,
        #         ],
        #     },
        #     {
        #         "type": "Days off",
        #         "data": [
        #             days_off,
        #             till_date_days,
        #         ],
        #     },
        # ],
    }
    return attendance_details

@frappe.whitelist()
def run_attendance_report(employee, company):
    filters = {
        "month": cstr(frappe.utils.getdate().month),
        "year": cstr(frappe.utils.getdate().year),
        "company": company,
        "employee": employee,
        "summarized_view": 1,
    }
    from frappe.desk.query_report import run

    attendance_report = run("Monthly Attendance Sheet", filters=filters)
    if attendance_report.get("result"):
        return attendance_report.get("result")[0]
    
@frappe.whitelist()
def get_activity_types():
    try:
        # Fetch all activity types from the Activity Type doctype
        activity_types = frappe.get_all(
            "Activity Type",  # Replace with your actual DocType name
            fields=["name"]  # Adjust fields as necessary
        )
        
        # If you want to format it in a specific way, you can do so here
        return gen_response(200, "Activity Types fetched successfully", activity_types)
    
    except Exception as e:
        # Handle exceptions and return an error response
        return gen_response(500, "Error fetching activity types", str(e))
    


@frappe.whitelist()
def create_attendance_request(*args, **kwargs):
    try:
        emp_data = get_employee_by_user(frappe.session.user)
        if not len(emp_data) >= 1:
            return gen_response(500, "Employee does not exists")
        validate_employee_data(emp_data)
        leave_application_doc = frappe.get_doc(
            dict(
                doctype="Attendance Request",
                employee=emp_data.get("name"),
                company=emp_data.company
            )
        )
        leave_application_doc.update(kwargs)
        res = leave_application_doc.insert()
        gen_response(200, "Attendance Request Successfully Added",res)

    except frappe.PermissionError:
        return gen_response(500, "Not permitted to manage attendance requests.")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_shift_list():
    try:
        shift_type_list = frappe.get_list("Shift Type", fields=["name"])
        gen_response(200, "Shift Type list get successfully", shift_type_list)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for shift")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_attendance_request_list(**data):
    try:
        employee = frappe.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        )
        if not employee:
            return gen_response(500, "Employee record not found.")

        filters = [["Attendance Request", "employee", "=", employee]]
        if data.get("filters"):
            filters.extend(data.get("filters"))

        attendance_request_list = frappe.get_all(
            "Attendance Request",
            filters=filters,
            fields=[
                "name",
                "employee",
                "docstatus",
                "employee_name",
                "department",
                "company",
                "from_date",
                "to_date",
                "half_day",
                "half_day_date",
                "include_holidays",
                "shift",
                "reason",
                "explanation",
            ],
        )

        for request in attendance_request_list:
            if request.get("from_date"):
                request["from_date"] = getdate(request["from_date"]).strftime(
                    "%d-%m-%Y"
                )
            if request.get("to_date"):
                request["to_date"] = getdate(request["to_date"]).strftime("%d-%m-%Y")

        return gen_response(
            200,
            "Attendance Request list retrieved successfully.",
            attendance_request_list,
        )
    except frappe.PermissionError as e:
        return gen_response(500, str(e))
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_attendance_request(request_id=None):
    if not request_id:
        return gen_response(500, "Request ID cannot be blank.")

    try:
        employee = frappe.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        )
        if not employee:
            return gen_response(500, "Employee record not found.")

        if not frappe.db.exists(
            "Attendance Request", {"name": request_id, "employee": employee}
        ):
            return gen_response(500, "Attendance Request Not found")

        request_doc = frappe.get_value(
            "Attendance Request",
            {"name": request_id, "employee": employee},
            [
                "name",
                "employee",
                "employee_name",
                "department",
                "company",
                "from_date",
                "to_date",
                "half_day",
                "half_day_date",
                "include_holidays",
                "shift",
                "reason",
                "explanation",
            ],
            as_dict=True,
        )
        if request_doc.get("from_date"):
            request_doc["from_date"] = getdate(request_doc["from_date"]).strftime(
                "%d-%m-%Y"
            )
        if request_doc.get("to_date"):
            request_doc["to_date"] = getdate(request_doc["to_date"]).strftime(
                "%d-%m-%Y"
            )
        gen_response(200, "Attendance Request details get successfully.", request_doc)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted to access attendance request")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def delete_attendance_request(name):
    if not name:
        return gen_response(500, "Request ID cannot be blank.")
    try:
        emp = get_employee_by_user(frappe.session.user,fields=["name","company"])
        if not emp:
            return gen_response(500, "Employee record not found.")
        validate_employee_data(emp)
        if not frappe.db.exists(
            "Attendance Request",
            {"name": name, "employee": emp.get("name")}
        ):
            frappe.throw("Attendance Request not found", frappe.PermissionError)
        doc = frappe.get_doc("Attendance Request", name)

        if doc.docstatus == 1:
            frappe.throw("Submitted attendance request cannot be deleted")

        doc.delete()
        return gen_response(200, "Attendance Request deleted successfully.")
    except frappe.PermissionError as e:
        return gen_response(500, str(e))
    except Exception as e:
        return exception_handel(e)