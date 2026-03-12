import json
import frappe
from frappe import _

from erpnext.accounts.utils import getdate
from mobile.mobile_env.app_utils import (
    gen_response,
    ess_validate,
    get_ess_settings,
    prepare_json_data,
    get_global_defaults,
    exception_handel,
)
from erpnext.accounts.party import get_dashboard_info

from frappe.utils import flt, today
import frappe

# -------------------------------
# Customer List
# -------------------------------
@frappe.whitelist()
def get_customer_list():
    try:
        customer_list = frappe.get_list(
            "Customer",
            filters={"custom_retailerdealer": "Dealer"},
            pluck="name",
        )
        return customer_list
    except Exception as e:
        return exception_handel(e)

#seolf orders 
@frappe.whitelist()
def get_self_orders_list():
    try:
        order_list = frappe.get_list(
            "Sales Order",
            filters={"owner": frappe.session.user},
           fields=["name","customer_name","transaction_date","grand_total","status","total_qty","set_warehouse","delivery_status","owner","delivery_date"],
        )
        return gen_response(200, "Order get successfully", order_list)
    except Exception as e:
        return exception_handel(e)

# -------------------------------
# Warehouse List
# -------------------------------
@frappe.whitelist()
def get_warehouselist():
    try:
        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")
        warehouselist = frappe.get_list(
            "Warehouse",
            pluck="name",
            filters={"company": company,"disabled":0,"is_group":0}
        )
        return warehouselist
    except Exception as e:
        return exception_handel(e)


# -------------------------------
# Item List
# -------------------------------
@frappe.whitelist()
def get_self_order_item_list():
    try:
        item_list = frappe.get_list(
            "Item",
            filters={
                "disabled": 0,
                "is_stock_item": 1,
            },
            fields=["name", "item_name", "item_code", "image"],
            order_by="item_name asc",
        )

        if not item_list:
            return api_response(True, "Item list fetched successfully", [])

        item_codes = [d.item_code for d in item_list if d.get("item_code")]

        stock_map = {}
        if item_codes:
            stock_data = frappe.db.sql(
                """
                SELECT
                    item_code,
                   price_list_rate AS rate
                FROM `tabItem Price`
                WHERE item_code IN %(item_codes)s AND price_list = 'Standard Selling'
                GROUP BY item_code
                """,
                {"item_codes": tuple(item_codes)},
                as_dict=True,
            )

            stock_map = {
                d.item_code: flt(d.rate)
                for d in stock_data
            }

        items = []
        for item in item_list:
            items.append({
                "name": item.get("name"),
                "item_name": item.get("item_name"),
                "item_code": item.get("item_code"),
                "image": item.get("image"),
                "rate": stock_map.get(item.get("item_code"), 0.0),
            })

        return gen_response(200, "Item list fetched successfully", items)
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_item_list(warehouse=None):
    try:
        item_list = frappe.get_list(
            "Item",
            fields=["name", "item_name", "item_code", "image"],
        )
        items = get_items_data(item_list, warehouse)
        return items
    except Exception as e:
        return exception_handel(e)




def get_items_data(items, warehouse):
    items_data = []
    for item in items:
        item_data = {
            "name": item.name,
            "item_name": item.item_name,
            "item_code": item.item_code,
            "image": item.image,
            "actual_qty": float(get_actual_qty(item.item_code, warehouse)),
            "rate": get_item_rate(item.item_code)
        }
        items_data.append(item_data)
    return items_data


def get_actual_qty(item_code, warehouse):
    bin_data = frappe.get_all(
        "Bin",
        filters={"item_code": item_code, "warehouse": warehouse},
        fields=["actual_qty", "warehouse"]
    )
    if bin_data:
        return bin_data[0].get("actual_qty", 0)
    return 0


def get_item_rate(item_code):
    item_price = frappe.get_all(
        "Item Price",
        filters={"item_code": item_code, "price_list": "Standard Selling"},
        fields=["price_list_rate"],
        order_by="creation desc",
        limit=1
    )
    if item_price:
        return item_price[0].get("price_list_rate", 0)
    return 0.0


# -------------------------------
# Masters (Combined Data)
# -------------------------------
@frappe.whitelist()
def distributor_masters():
    try:
        meta_data = {
            "customers": get_customer_list(),
            "items": get_item_list(),
            "warehouses": get_warehouselist()
        }

        return gen_response(200, "Master get successfully", meta_data)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for masters")
    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist()
def masters():
    try:
        meta_data = {
            "customers": get_customer_list(),
            "items": get_item_list(),
            "warehouses": get_warehouselist()
        }

        return gen_response(200, "Master get successfully", meta_data)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for masters")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def prepare_order_totals(**kwargs):
    try:
        data = kwargs
        if not data.get("customer"):
            return gen_response(500, "Customer is required.")
        # ess_settings = get_ess_settings()
        # default_warehouse = ess_settings.get("default_warehouse")
        delivery_date = data.get("delivery_date")
        for item in data.get("items"):
            item["delivery_date"] = delivery_date
            item["warehouse"] = data.get("set_warehouse")
        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")
        sales_order_doc = frappe.get_doc(dict(doctype="Sales Order", company=company))
        sales_order_doc.update(data)
        sales_order_doc.run_method("set_missing_values")
        sales_order_doc.run_method("calculate_taxes_and_totals")
        order_data = (
            prepare_json_data(
                [
                    "taxes_and_charges",
                    "total_taxes_and_charges",
                    "net_total",
                    "discount_amount",
                    "grand_total",
                ],
                json.loads(sales_order_doc.as_json()),
            ),
        )
        gen_response(200, "Order details get successfully", order_data)
    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def prepare_selforder_totals(**kwargs):
    try:
        data = frappe._dict(kwargs)

        # Get mapped customer + warehouse for logged-in user
        customer_info = frappe.db.get_value(
            "Customer Warehouse",
            {"user": frappe.session.user},
            ["warehouse", "customer"],
            as_dict=1
        )

        customer = customer_info.customer if customer_info else None
        warehouse = customer_info.warehouse if customer_info else None

        if not customer:
            return gen_response(500, "Customer is required.")

        if not warehouse:
            return gen_response(500, "Warehouse is required.")

        items = data.get("items") or []
        if not items:
            return gen_response(500, "Items are required.")

        delivery_date = data.get("delivery_date") or today()

        # Force customer and warehouse from mapping
        data["customer"] = customer
        data["set_warehouse"] = warehouse
        data["delivery_date"] = delivery_date

        for item in items:
            item["delivery_date"] = delivery_date
            item["warehouse"] = warehouse

        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")

        if not company:
            return gen_response(500, "Default company is not set.")

        sales_order_doc = frappe.get_doc(dict(doctype="Sales Order", company=company))
        sales_order_doc.update(data)
        sales_order_doc.flags.ignore_permissions = True
        sales_order_doc.run_method("set_missing_values")
        sales_order_doc.run_method("calculate_taxes_and_totals")

        order_data = prepare_json_data(
            [
                "taxes_and_charges",
                "total_taxes_and_charges",
                "net_total",
                "discount_amount",
                "grand_total",
            ],
            json.loads(sales_order_doc.as_json()),
        )

        return gen_response(200, "Order details fetched successfully", order_data)

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def get_order_list():
    try:
        order_list = frappe.get_list(
            "Sales Order",
            fields=[
                "name",
                "customer_name",
                "DATE_FORMAT(transaction_date, '%d-%m-%Y') as transaction_date",
                "grand_total",
                "status",
                "total_qty",
            ],
             order_by='creation desc',
        )
        gen_response(200, "Order list get successfully", order_list)
    except Exception as e:
        return exception_handel(e)




@frappe.whitelist()
def create_order(**kwargs):
    try:
        data = kwargs
        if not data.get("customer"):
            return gen_response(500, "Customer is required.")
        if not data.get("items") or len(data.get("items")) == 0:
            return gen_response(500, "Please select items to proceed.")
        if not data.get("delivery_date"):
            return gen_response(500, "Please select delivery date to proceed.")

        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")
        # ess_settings = get_ess_settings()
        # default_warehouse = ess_settings.get("default_warehouse")
        
        if data.get("name"):
            if not frappe.db.exists("Sales Order", data.get("name"), cache=True):
                return gen_response(500, "Invalid order id.")
            sales_order_doc = frappe.get_doc("Sales Order", data.get("name"))
            delivery_date = data.get("delivery_date")
            # for item in data.get("items"):
            #     item["delivery_date"] = delivery_date
            #     item["warehouse"] = default_warehouse
            sales_order_doc.update(data)
            sales_order_doc.run_method("set_missing_values")
            sales_order_doc.run_method("calculate_taxes_and_totals")
            sales_order_doc.save()
            gen_response(200, "Order updated successfully.", sales_order_doc)
           
        else:
            sales_order_doc = frappe.get_doc(
                dict(doctype="Sales Order", company=company)
            )
            delivery_date = data.get("delivery_date")
            # for item in data.get("items"):
            #     item["delivery_date"] = delivery_date
            #     item["warehouse"] = default_warehouse
            sales_order_doc.update(data)
            sales_order_doc.run_method("set_missing_values")
            sales_order_doc.run_method("calculate_taxes_and_totals")
            sales_order_doc.insert()

            if data.get("attachments") is not None:
                for file in data.get("attachments"):
                    file_doc = frappe.get_doc(
                        {
                            "doctype": "File",
                            "file_url": file.get("file_url"),
                            "attached_to_doctype": "Sales Order",
                            "attached_to_name": sales_order_doc.name,
                        }
                    )
                    file_doc.insert(ignore_permissions=True)
            gen_response(200, "Order created successfully.", sales_order_doc)

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist()
def create_delivery_note(**kwargs):
    try:
        data = kwargs

        if not data.get("customer"):
            return gen_response(500, "Customer is required.")
        if not data.get("items") or len(data.get("items")) == 0:
            return gen_response(500, "Please select items to proceed.")

        global_defaults = get_global_defaults()
        company = global_defaults.get("default_company")

        # Always create new Delivery Note
        dn = frappe.get_doc(dict(doctype="Delivery Note", company=company))
        dn.update(data)
        dn.run_method("set_missing_values")
        dn.run_method("calculate_taxes_and_totals")
        dn.insert()

        # Try submitting
        dn.submit()

        return gen_response(200, "Delivery Note created and submitted successfully.", dn.as_dict())

    except Exception as e:
        frappe.db.rollback()  # rollback in case insert partially happened
        return exception_handel(e)

