// Copyright (c) 2023, Qunatbit and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Location", {
	onload(frm) {
		// Do not recalculate on every refresh; it can overwrite a valid saved route
		// with fallback straight-line geometry if route API is unavailable.
		if (frm.is_new()) {
			frm.call({
				method: "calculate_distance",
				doc: frm.doc,
			});
		}
	},
	refresh(frm) {
		render_employee_location_map(frm);
	},
	location_table_remove(frm) {
		render_employee_location_map(frm);
	},
});

frappe.ui.form.on("employee location table", {
	latitude(frm) {
		render_employee_location_map(frm);
	},
	longitude(frm) {
		render_employee_location_map(frm);
	},
	location_table_add(frm) {
		render_employee_location_map(frm);
	},
});

function render_employee_location_map(frm) {
	const wrapper = frm.fields_dict.my_location?.$wrapper;
	if (!wrapper) {
		return;
	}

	const points = get_points(frm.doc.location_table);
	if (!points.length) {
		wrapper.html(`<div style="padding: 12px; color: #6b7280;">Location not available yet.</div>`);
		return;
	}

	const src = build_google_embed_src(points);
	const html = `
		<div style="width: 100%; height: 360px; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden;">
			<iframe
				title="Employee Route Map"
				width="100%"
				height="360"
				frameborder="0"
				style="border:0"
				src="${src}"
				allowfullscreen
			></iframe>
		</div>
	`;

	wrapper.html(html);
}

function get_points(rows) {
	const result = [];
	(rows || []).forEach((row) => {
		const lat = parse_coordinate(row.latitude);
		const lng = parse_coordinate(row.longitude);
		if (lat == null || lng == null) {
			return;
		}
		result.push({ lat, lng });
	});
	return result;
}

function parse_coordinate(value) {
	const parsed = Number.parseFloat(value);
	return Number.isFinite(parsed) ? parsed : null;
}

function build_google_embed_src(points) {
	if (points.length === 1) {
		const p = points[0];
		return `https://maps.google.com/maps?q=${p.lat},${p.lng}&z=17&output=embed`;
	}

	const origin = points[0];
	const destinations = points.slice(1).map((p) => `${p.lat},${p.lng}`);
	const daddr = destinations.join("+to:");
	return `https://maps.google.com/maps?saddr=${origin.lat},${origin.lng}&daddr=${daddr}&output=embed`;
}
