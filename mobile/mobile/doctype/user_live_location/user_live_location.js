// Copyright (c) 2026, Sanpra Software Solution and contributors
// For license information, please see license.txt

frappe.ui.form.on("User Live Location", {
	refresh(frm) {
		render_location_map(frm);
	},
	get_location(frm) {
		const apply_location_data = async (data, coords) => {
			const parse_coord = (value) => {
				const parsed = Number.parseFloat(value);
				return Number.isFinite(parsed) ? parsed : null;
			};

			const userLat = parse_coord(data.user?.latitude);
			const userLng = parse_coord(data.user?.longitude);
			const loginLat = parse_coord(coords?.latitude ?? data.login_user?.latitude);
			const loginLng = parse_coord(coords?.longitude ?? data.login_user?.longitude);

			const [userAddress, loginUserAddress] = await Promise.all([
				reverse_geocode(userLat, userLng),
				reverse_geocode(loginLat, loginLng),
			]);

			let distanceKm = parse_coord(data.distance);
			if (userLat != null && userLng != null && loginLat != null && loginLng != null) {
				const computed = get_distance_km(userLat, userLng, loginLat, loginLng);
				if (Number.isFinite(computed)) {
					distanceKm = computed;
				}
			} else {
				distanceKm = distanceKm ?? null;
			}

			frm.set_value({
				user_latitude: userLat,
				user_longitude: userLng,
				login_user_latitude: loginLat,
				login_user_longitude: loginLng,
				user_address: userAddress,
				login_user_address: loginUserAddress,
				distance: distanceKm,
			});
		};

		get_current_location()
			.then((coords) => {
				if (coords) {
					frm.set_value({
						login_user_latitude: coords.latitude,
						login_user_longitude: coords.longitude,
					});
				}
				return frm.call({
					method: "get_employee_location",
					doc: frm.doc,
					args: {
						login_latitude: coords?.latitude || null,
						login_longitude: coords?.longitude || null,
					},
				}).then((r) => ({ r, coords }));
			})
			.then(({ r, coords }) => {
				if (r?.message) {
					return apply_location_data(r.message, coords).then(() => render_location_map(frm));
				}
				render_location_map(frm);
			})
			.catch((err) => {
				frappe.msgprint(err?.message || "Unable to get current location.");
				frm.set_value({
					login_user_latitude: null,
					login_user_longitude: null,
					login_user_address: null,
					distance: null,
				});
				frm.call({
					method: "get_employee_location",
					doc: frm.doc,
				}).then((r) => {
					if (r?.message) {
						return apply_location_data(r.message, null).then(() => render_location_map(frm));
					}
					render_location_map(frm);
				});
			});
	},


	// setup: function(frm) {
    //     frm.set_query("user", function() {
    //         return {
    //             query: "crmhr.crm_and_hr.doctype.user_live_location.user_live_location.get_users_by_company_permission"
    //         };
    //     });
    // }
	
});

function get_current_location() {
	return new Promise((resolve, reject) => {
		if (!navigator.geolocation) {
			reject(new Error("Geolocation is not supported in this browser."));
			return;
		}
		navigator.geolocation.getCurrentPosition(
			(pos) => {
				resolve({
					latitude: pos.coords.latitude,
					longitude: pos.coords.longitude,
				});
			},
			(err) => {
				reject(new Error(err?.message || "Location permission denied."));
			},
			{
				enableHighAccuracy: true,
				timeout: 10000,
				maximumAge: 0,
			}
		);
	});
}

function render_location_map(frm) {
	const userLat = Number.parseFloat(frm.doc.user_latitude);
	const userLng = Number.parseFloat(frm.doc.user_longitude);
	const loginLat = Number.parseFloat(frm.doc.login_user_latitude);
	const loginLng = Number.parseFloat(frm.doc.login_user_longitude);
	const wrapper = frm.fields_dict.location?.$wrapper;

	if (!wrapper) {
		return;
	}

	if (
		!Number.isFinite(userLat) ||
		!Number.isFinite(userLng) ||
		!Number.isFinite(loginLat) ||
		!Number.isFinite(loginLng)
	) {
		wrapper.html(
			`<div style="padding: 12px; color: #6b7280;">Location not available yet.</div>`
		);
		return;
	}

	const samePoint =
		Math.abs(Number(userLat) - Number(loginLat)) < 0.000001 &&
		Math.abs(Number(userLng) - Number(loginLng)) < 0.000001;

	const src = samePoint
		? `https://maps.google.com/maps?q=${userLat},${userLng}&z=17&output=embed`
		: `https://maps.google.com/maps?saddr=${userLat},${userLng}&daddr=${loginLat},${loginLng}&output=embed`;
	const html = `
		<div style="width: 100%; height: 360px; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden;">
			<iframe
				title="User Location Map"
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

function get_distance_km(lat1, lon1, lat2, lon2) {
	const toRad = (v) => (Number(v) * Math.PI) / 180;
	const r = 6371;
	const dLat = toRad(lat2 - lat1);
	const dLon = toRad(lon2 - lon1);
	const a =
		Math.sin(dLat / 2) * Math.sin(dLat / 2) +
		Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
	const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
	return r * c;
}

function reverse_geocode(latitude, longitude) {
	if (latitude == null || longitude == null) {
		return Promise.resolve(null);
	}

	const key = "de1bf3be66b546b89645e500ec3a3a28";
	const url = `https://api.opencagedata.com/geocode/v1/json?q=${latitude}+${longitude}&key=${key}`;

	return fetch(url)
		.then((response) => response.json())
		.then((data) => {
			if (data?.results?.length) {
				const result = data.results[0];
				return result.formatted;
			}
			return null;
		})
		.catch(() => null);
}
