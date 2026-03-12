# Copyright (c) 2023, Qunatbit and contributors
# For license information, please see license.txt
import frappe
import requests
import json
from math import atan2, cos, radians, sin, sqrt
from frappe.model.document import Document

class EmployeeLocation(Document):
	def validate(self):
		self.calculate_distance()
	
	# ======================19/01/2026=======================
	def after_insert(self):
		self.get_address_from_lat_long()

	def on_update(self):
		self.get_address_from_lat_long() 
	# def before_save(self): 
	# 	self.get_address_from_lat_long()

	def get_address_from_lat_long(self):
		for row in self.location_table:
			if row.latitude and row.longitude and not row.address:
				url = "https://nominatim.openstreetmap.org/reverse"
				params = {
					"lat": row.latitude,
					"lon": row.longitude,
					"format": "json"
				}
				headers = {"User-Agent": "Frappe"}

				res = requests.get(url, params=params, headers=headers, timeout=10)
				if res.status_code == 200:
					address = res.json().get("display_name", "")
					if address:
						frappe.db.set_value("employee location table",row.name,"address",address)
		# =====================19/01/2026=======================

	def set_map_location(self, coordinates=None):
		location_list = coordinates
		if location_list is None:
			location_list = [[lng, lat] for lng, lat in self._get_point_list()]

		if not location_list:
			self.my_location = None
			return

		map_json = {
			"type": "FeatureCollection",
			"features": [
				{
					"type": "Feature",
					"properties": {},
					"geometry": {
						"type": "LineString",
						"coordinates": location_list,
					},
				},
				{
					"type": "Feature",
					"properties": {},
					"geometry": {
						"type": "Point",
						"coordinates": location_list[0],
					},
				},
			],
		}

		self.my_location = json.dumps(map_json)

	@frappe.whitelist()
	def calculate_distance(self):
		point_rows = self._get_point_rows()
		points = [(lng, lat) for _, lng, lat in point_rows]
		self._reset_row_distances()

		if not points:
			self.distance = 0
			self.my_location = None
			return

		point_rows[0][0].distance_km = 0
		if len(points) == 1:
			self.distance = 0
			self.set_map_location()
			return

		api_key = '1cfcdeaf26352898f9975a577da9fd30'
		headers = {'accept': 'application/json'}
		total_distance_km = 0.0

		for index in range(1, len(point_rows)):
			_, start_lng, start_lat = point_rows[index - 1]
			current_row, end_lng, end_lat = point_rows[index]
			segment_distance_km = self._get_segment_distance_km(
				api_key, headers, start_lng, start_lat, end_lng, end_lat
			)
			if segment_distance_km is None:
				segment_distance_km = self._haversine_km(
					start_lat, start_lng, end_lat, end_lng
				)

			total_distance_km += float(segment_distance_km or 0)
			current_row.distance_km = round(total_distance_km, 2)

		self.distance = round(total_distance_km, 2)

		route_coordinates = self._build_route_coordinates(api_key, headers, points)
		if route_coordinates:
			self.set_map_location(route_coordinates)
		else:
			self.set_map_location()

	def _get_segment_distance_km(self, api_key, headers, start_lng, start_lat, end_lng, end_lat):
		distance_km = self._get_distance_km_from_route_coords(
			api_key, start_lng, start_lat, end_lng, end_lat, headers
		)
		if distance_km is None:
			distance_km = self._get_distance_km_from_matrix_coords(
				api_key, start_lng, start_lat, end_lng, end_lat, headers
			)
		return distance_km

	def _get_distance_km_from_route_coords(
		self, api_key, start_lng, start_lat, end_lng, end_lat, headers
	):
		route = self._get_route(api_key, start_lng, start_lat, end_lng, end_lat, headers)
		if not route:
			return None

		distance_meters = route.get("distance")
		if distance_meters is None:
			return None

		return float(distance_meters) / 1000.0

	def _get_route(self, api_key, start_lng, start_lat, end_lng, end_lat, headers):
		route = self._request_route(
			api_key, start_lng, start_lat, end_lng, end_lat, headers
		)
		if route:
			return route

		# Some routing APIs expect lat,lng instead of lng,lat.
		route = self._request_route(
			api_key, start_lat, start_lng, end_lat, end_lng, headers
		)
		if route:
			return route

		# Final fallback: OSRM public route API.
		return self._request_osrm_route(start_lng, start_lat, end_lng, end_lat)

	def _request_route(self, api_key, start_first, start_second, end_first, end_second, headers):
		url = (
			f"https://apis.mappls.com/advancedmaps/v1/{api_key}/route_adv/driving/"
			f"{start_first},{start_second};"
			f"{end_first},{end_second}"
		)
		params = {
			"geometries": "polyline",
			"overview": "full",
		}
		response = requests.get(url, headers=headers, params=params, timeout=10)
		if response.status_code != 200:
			return None

		response_data = response.json()
		if response_data.get("routes"):
			return response_data["routes"][0]
		if response_data.get("route"):
			return response_data["route"]

		return None

	def _request_osrm_route(self, start_lng, start_lat, end_lng, end_lat):
		url = (
			"https://router.project-osrm.org/route/v1/driving/"
			f"{start_lng},{start_lat};{end_lng},{end_lat}"
		)
		params = {
			"overview": "full",
			"geometries": "geojson",
		}
		response = requests.get(url, params=params, timeout=10)
		if response.status_code != 200:
			return None

		data = response.json()
		routes = data.get("routes") or []
		if not routes:
			return None

		return routes[0]

	def _get_distance_km_from_matrix_coords(
		self, api_key, start_lng, start_lat, end_lng, end_lat, headers
	):
		distance = self._request_distance_matrix(
			api_key, start_lng, start_lat, end_lng, end_lat, headers
		)
		if distance is not None:
			return distance

		# Retry with lat,lng ordering.
		return self._request_distance_matrix(
			api_key, start_lat, start_lng, end_lat, end_lng, headers
		)

	def _request_distance_matrix(
		self, api_key, start_first, start_second, end_first, end_second, headers
	):
		url = (
			f"https://apis.mappls.com/advancedmaps/v1/{api_key}/distance_matrix/driving/"
			f"{start_first},{start_second};"
			f"{end_first},{end_second}?rtype=0&region=IND"
		)
		response = requests.get(url, headers=headers, timeout=10)
		if response.status_code != 200:
			return None

		response_data = response.json()
		distances = response_data.get("results", {}).get("distances")
		if not distances or not distances[0]:
			return None

		return float(distances[0][1]) / 1000.0

	def _build_route_coordinates(self, api_key, headers, points):
		if len(points) < 2:
			return None

		route_coordinates = []
		for index in range(len(points) - 1):
			start_lng, start_lat = points[index]
			end_lng, end_lat = points[index + 1]
			segment_coordinates = self._get_route_coordinates(
				api_key, start_lng, start_lat, end_lng, end_lat, headers
			)
			if not segment_coordinates:
				segment_coordinates = [
					[start_lng, start_lat],
					[end_lng, end_lat],
				]

			if route_coordinates and segment_coordinates:
				if route_coordinates[-1] == segment_coordinates[0]:
					route_coordinates.extend(segment_coordinates[1:])
				else:
					route_coordinates.extend(segment_coordinates)
			else:
				route_coordinates.extend(segment_coordinates)

		return route_coordinates

	def _get_route_coordinates(self, api_key, start_lng, start_lat, end_lng, end_lat, headers):
		route = self._get_route(api_key, start_lng, start_lat, end_lng, end_lat, headers)
		if not route:
			return None

		geometry = route.get("geometry")
		if isinstance(geometry, dict):
			coordinates = geometry.get("coordinates")
			if coordinates:
				return self._normalize_route_coordinates(
					coordinates, start_lng, start_lat
				)
		if isinstance(geometry, list):
			return self._normalize_route_coordinates(
				geometry, start_lng, start_lat
			)

		polyline_value = geometry
		if not polyline_value:
			polyline_value = route.get("polyline")
		if isinstance(polyline_value, dict):
			polyline_value = polyline_value.get("points")

		if isinstance(polyline_value, str) and polyline_value:
			decoded = self._decode_polyline(polyline_value)
			return [[lng, lat] for lat, lng in decoded]

		return None

	def _normalize_route_coordinates(self, coordinates, start_lng, start_lat):
		if not coordinates:
			return None

		pairs = []
		for item in coordinates:
			if not isinstance(item, (list, tuple)) or len(item) < 2:
				continue
			first = self._to_float(item[0])
			second = self._to_float(item[1])
			if first is None or second is None:
				continue
			pairs.append([first, second])

		if not pairs:
			return None

		first, second = pairs[0]
		swap = False
		if abs(first) <= 90 and abs(second) > 90:
			swap = True
		elif abs(first) <= 90 and abs(second) <= 90:
			unswapped_delta = abs(first - start_lng) + abs(second - start_lat)
			swapped_delta = abs(second - start_lng) + abs(first - start_lat)
			swap = swapped_delta < unswapped_delta

		if not swap:
			return pairs

		return [[second, first] for first, second in pairs]

	def _decode_polyline(self, polyline_str):
		index = 0
		lat = 0
		lng = 0
		coordinates = []

		while index < len(polyline_str):
			shift = 0
			result = 0
			while True:
				b = ord(polyline_str[index]) - 63
				index += 1
				result |= (b & 0x1f) << shift
				shift += 5
				if b < 0x20:
					break
			delta_lat = ~(result >> 1) if (result & 1) else (result >> 1)
			lat += delta_lat

			shift = 0
			result = 0
			while True:
				b = ord(polyline_str[index]) - 63
				index += 1
				result |= (b & 0x1f) << shift
				shift += 5
				if b < 0x20:
					break
			delta_lng = ~(result >> 1) if (result & 1) else (result >> 1)
			lng += delta_lng

			coordinates.append((lat / 1e5, lng / 1e5))

		return coordinates

	def _get_point_list(self):
		points = []
		for location in self.location_table or []:
			lng = self._to_float(location.longitude)
			lat = self._to_float(location.latitude)
			if lng is None or lat is None:
				continue
			points.append((lng, lat))
		return points

	def _get_point_rows(self):
		points = []
		for location in self.location_table or []:
			lng = self._to_float(location.longitude)
			lat = self._to_float(location.latitude)
			if lng is None or lat is None:
				continue
			points.append((location, lng, lat))
		return points

	def _reset_row_distances(self):
		for location in self.location_table or []:
			location.distance_km = None

	def _haversine_km(self, lat1, lon1, lat2, lon2):
		radius_km = 6371.0
		d_lat = radians(lat2 - lat1)
		d_lon = radians(lon2 - lon1)
		lat1_rad = radians(lat1)
		lat2_rad = radians(lat2)
		a = sin(d_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(d_lon / 2) ** 2
		c = 2 * atan2(sqrt(a), sqrt(1 - a))
		return radius_km * c

	def _to_float(self, value):
		if value is None:
			return None
		if isinstance(value, (int, float)):
			return float(value)
		if isinstance(value, str):
			value = value.strip()
			if not value:
				return None
			try:
				return float(value)
			except ValueError:
				return None
		return None
