import requests
from math import radians, cos, sin, asin, sqrt, ceil

def haversine(lat1, lon1, lat2, lon2):
    """
    Возвращает расстояние между двумя точками в км (float).
    """
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def calc_delivery_cost(distance_km: float) -> int:
    """
    Для теста: первый км — 1 руб, далее +1 руб/км (округляем вверх)
    """
    return max(1, ceil(distance_km))

def prettify_address(address_json):
    """Вернёт короткий адрес: улица, дом, город"""
    if not address_json:
        return None
    address = address_json.get("address", {})
    road = address.get("road") or address.get("pedestrian") or ""
    house_number = address.get("house_number") or ""
    suburb = address.get("suburb") or ""
    city = address.get("city") or address.get("town") or address.get("village") or ""
    # Собираем адрес красиво:
    parts = []
    if road:
        if house_number:
            parts.append(f"{road}, {house_number}")
        else:
            parts.append(road)
    elif house_number:
        parts.append(house_number)
    if suburb:
        parts.append(suburb)
    if city:
        parts.append(city)
    return ", ".join(parts) if parts else None




def get_address_from_coords(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "format": "json",
        "lat": lat,
        "lon": lon,
        "zoom": 18,
        "addressdetails": 1,
    }
    headers = {
        "User-Agent": "pizza-bot/1.0"
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=7)
        data = resp.json()
        # передаем не весь data, а только address, но твой prettify_address работает и с data
        short_addr = prettify_address(data)
        if short_addr:
            return short_addr
        # если не удалось — возвращаем полный адрес
        return data.get("display_name")
    except Exception as e:
        print(f"Ошибка при получении адреса: {e}")
        return None


