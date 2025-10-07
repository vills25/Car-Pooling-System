from datetime import timedelta
from django.forms import ValidationError
from django.utils import timezone
import random
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.response import Response
import requests
from .models import Activity, Booking, CreateCarpool
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings
from geopy.geocoders import Nominatim
from math import atan2, radians, cos, sin, sqrt
from geopy.distance import geodesic
from django.db.models import Q
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

def user_is_admin(user):
    """
    Check if a user is an admin or has superuser privileges.

    Returns:
    bool: True if the user is an admin or has superuser privileges, False otherwise.
    """
    return user.role == "admin" or getattr(user, "is_superuser", False)

## Save activity log
def activity(user, details):
    """
    Save activity log for user.
    """
    try:
        Activity.objects.create(user=user, details=details)
    except Exception as e:
        print("Activity log failed:", str(e))

## Generate random OTP (6 digit)
def generate_otp():
    return str(random.randint(100000, 999999))

## Send OTP email
def send_otp_email(email, otp):
    """
    Send an email with an OTP to the given email address.

    Parameters:
    email (str): The email address to which the OTP should be sent.
    otp (str): The OTP to be sent.

    Returns:
    bool: True if the email is sent successfully, False otherwise.
    """
    subject = "Your OTP Code"
    message = f"Your OTP for password reset is: {otp}. It will expire in 10 minutes."
    from_email = "vishalsohaliya25@gmail.com"
    try:
        send_mail(subject, message, from_email, [email])
        return True
    except Exception as e:
        print("Email send failed:", str(e))
        return False

## Add INR and KM units to contribution_per_km and distance_km.
def km_inr_format(data):
    """
    Add INR and KM units to contribution_per_km and distance_km.
    Parameters:
    data (list or dict): The data to be formatted. If it is a list, all the items in it will be formatted.
    Returns:
    list or dict: The formatted data.
    """
    # if isinstance(data, list):
    #     for km_inr in data:
    #         if km_inr.get("contribution_per_km"):
    #             km_inr["contribution_per_km"] = f"{km_inr['contribution_per_km']} INR"
    #         if km_inr.get("distance_km"):
    #             km_inr["distance_km"] = f"{km_inr['distance_km']} KM"
    #     return data
    # return data

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                for item in value:
                    if item.get("contribution_per_km") is not None:
                        item["contribution_per_km"] = f"{item['contribution_per_km']} INR"
                    if item.get("distance_km") is not None:
                        item["distance_km"] = f"{item['distance_km']} KM"
            elif isinstance(value, dict):
                data[key] = km_inr_format(value)
        return data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                km_inr_format(item)
        return data
    return data

## send Email for booking confirmed / rejected / waitlisted / cancelled
def send_booking_email(booking, status_type):
    subject = ""
    html_message = ""
    passenger_email = booking.passenger_name.email
    carpool = booking.carpool_driver_name

    if status_type == "confirmed":
        subject = "✅ Carpool Booking Confirmed"
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height:1.6; color:#333;">
            <h2 style="color: #27AE60;">✅ Booking Confirmed</h2>
            <p>Hello <b>{booking.passenger_name.first_name}</b>,</p>
            <p>Your booking has been successfully confirmed.</p>

            <table style="border-collapse: collapse; margin: 10px 0; width: 100%;">
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Booking ID:</td>
                    <td style="padding: 6px;">{booking.booking_id}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Journey:</td>
                    <td style="padding: 6px;">{carpool.start_location} ➝ {carpool.end_location}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Departure Time:</td>
                    <td style="padding: 6px;">{carpool.departure_time.strftime('%d %b %Y, %I:%M %p')}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Seats Booked:</td>
                    <td style="padding: 6px;">{booking.seat_book}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold;">Total Fare:</td>
                    <td style="padding: 6px;">₹ {booking.contribution_amount}</td>
                </tr>
            </table>

            <p style="margin-top: 10px;">We wish you a <b>Happy Journey!</b> 🚗</p>
            <p style="font-size: 12px; color: #888;">Customer Helpline: 1800-000-000 | +91 9856896548</p>
        </body>
        </html>
        """

    elif status_type == "rejected":
        subject = "❌ Carpool Booking Rejected"
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color:#333;">
            <h2 style="color: #E74C3C;">❌ Booking Rejected</h2>
            <p>Hello <b>{booking.passenger_name.first_name}</b>,</p>
            <p>Your booking <b>ID: {booking.booking_id}</b> was rejected by the driver.</p>
            <p style="font-size: 12px; color: #888;">You can try booking another available ride.</p>
        </body>
        </html>
        """

    elif status_type == "waitlisted":
        subject = "⏳ Carpool Booking Waitlisted"
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color:#333;">
            <h2 style="color: #F39C12;">⏳ Booking Waitlisted</h2>
            <p>Hello <b>{booking.passenger_name.first_name}</b>,</p>
            <p>Your booking <b>ID: {booking.booking_id}</b> is currently waitlisted due to no available seats.</p>
            <p>You can wait for availability or cancel and find another ride.</p>
            <p style="font-size: 12px; color: #888;">Customer Helpline: 1800-000-000 | +91 9856896548</p>
        </body>
        </html>
        """

    elif status_type == "cancelled":
        subject = "🚫 Carpool Booking Cancelled"
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color:#333;">
            <h2 style="color: #C0392B;">🚫 Booking Cancelled</h2>
            <p>Hello <b>{booking.passenger_name.first_name}</b>,</p>
            <p>Your booking <b>ID: {booking.booking_id}</b> has been cancelled.</p>
            <p style="font-size: 12px; color: #888;">Customer Helpline: 1800-000-000 | +91 9856896548</p>
        </body>
        </html>
        """

    try:
        # fallback plain text
        text_message = strip_tags(html_message)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[passenger_email]
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
    except Exception as e:
        print("Email send failed:", e)

## Helper function for Ride status 
def ride_status_function(request=None):
    """
    Auto update ride + booking status for all carpools and bookings
    based on time, driver action, and passenger action.
    """
    current_time = timezone.now()
    carpools = CreateCarpool.objects.all()

    for carpool in carpools:
        start = carpool.departure_time
        end = carpool.arrival_time
        original_status = carpool.carpool_ride_status

        #  Not started yet but departure passed 
        if carpool.carpool_ride_status == "upcoming" and start <= current_time < end:
            carpool.carpool_ride_status = "not_started_yet"

        #  Ride cancelled, if not started by arrival time 
        elif carpool.carpool_ride_status in ["upcoming", "not_started_yet"] and current_time >= end:
            carpool.carpool_ride_status = "cancelled"

        #  Auto complete rides active but 1 hour past arrival 
        elif carpool.carpool_ride_status == "active" and current_time > (end + timedelta(hours=1)):
            carpool.carpool_ride_status = "auto_completed"

        #  Save only if changed
        if carpool.carpool_ride_status != original_status:
            carpool.save()

        #  Update all bookings 
        bookings = Booking.objects.filter(carpool_driver_name=carpool)
        for booking in bookings:
            # Passenger cancelled
            if booking.booking_status == "cancelled":
                booking.ride_status = "cancelled"

            # Ride cancelled by driver/system
            elif carpool.carpool_ride_status == "cancelled":
                if booking.booking_status in ["pending", "waitlisted", "confirmed"]:
                    booking.ride_status = "did_not_travelled"
                    booking.booking_status = "cancelled"

            # Ride active
            elif carpool.carpool_ride_status == "active":
                booking.ride_status = "active"

            # Ride completed
            elif carpool.carpool_ride_status in ["completed", "auto_completed"]:
                if booking.booking_status == "confirmed":
                    booking.ride_status = "completed"

                elif booking.booking_status in ["pending", "waitlisted"]:
                    booking.ride_status = "did_not_travelled"
                    booking.booking_status = "cancelled"
                    
            # Ride not started yet
            elif carpool.carpool_ride_status == "not_started_yet" and current_time > start:
                if booking.booking_status in ["pending", "waitlisted", "confirmed"]:
                    booking.ride_status = "upcoming"

            # Upcoming
            elif current_time < start:
                booking.ride_status = "upcoming"

            booking.save()

## send/receive contacts form from user to admin.
def send_contact_email(name, email, phone_number, your_message):
    """
    Send an email to admin with contact form details.

    Parameters:
    name (str): Name of the user who submitted the contact form.
    email (str): Email of the user who submitted the contact form.
    phone_number (str): Phone number of the user who submitted the contact form.
    your_message (str): Message from the user who submitted the contact form.
    """
    subject = "Contact us form"
    message = f"Name: {name}\nEmail: {email}\nPhone Number: {phone_number}\nMessage: {your_message}"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = settings.DEFAULT_FROM_EMAIL
    send_mail(subject, message, from_email, [to_email])

## validate images size and type(jpg, png, jpeg)
def validate_image(image):
    allowed_extensions = ['jpg', 'png', 'jpeg']
    image_extension = image.name.split('.')[-1].lower()
    if image_extension not in allowed_extensions:
        raise ValidationError(f"Invalid image format. Allowed formats: {', '.join(allowed_extensions)}")
    
    if image.size > 2 * 1024 * 1024:
        raise ValidationError("Image size should not exceed 2MB.")

OSRM_BASE_URL = "http://router.project-osrm.org"  # public demo server; for production consider self-hosting

## get location latitude and longitude from entered string
def get_lat_lng(place_name):
    """
    Returns latitude/longitude cordinates for place name, else (None, None)
    param query: The address, query or a structured query
            you wish to geocode.
            For a structured query, provide a dictionary whose keys
            are one of: `street`, `city`, `county`, `state`, `country`, or
            `postalcode`.
    """
    geolocator = Nominatim(user_agent="carpool_app")
    try:
        loc = geolocator.geocode(place_name)
        if loc:
            return loc.latitude, loc.longitude
    except Exception as e:
        return Response({"status":"error", "message": f"Geocoding failed for {place_name}: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return None, None

location_cache = {}
def get_lat_lng_cached(location_name):
    """
    Return cached lat/lng if exists, else geocode and cache it.
    """
    if location_name in location_cache:
        return location_cache[location_name]

    lat, lon = get_lat_lng(location_name)
    location_cache[location_name] = (lat, lon)
    return lat, lon

def get_road_distance_osrm(lat1, lon1, lat2, lon2, profile="driving"):
    """
    Use OSRM public API to fetch by-road distance (in KM).
    Returns float km or None on failure.
    """
    try:
        # OSRM order: longitude, latitude
        coordinates = f"{lon1},{lat1};{lon2},{lat2}"
        url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coordinates}?overview=false&annotations=distance"
        resp = requests.get(url, timeout=6)
        if resp.status_code != 200:
            print("OSRM request failed:", resp.status_code)
            return None
        data = resp.json()
        # print("=========>>>>>>> OSRM response <<<<<<<=========:", data)

        if "routes" in data and len(data["routes"]) > 0:
            distance_m = data["routes"][0].get("distance")
            if distance_m is None:
                return None
            return round(distance_m / 1000.0, 2)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return None

## Calculate realistic distance between two points in km.
def calculate_realistic_distance(lat1, lon1, lat2, lon2):
    """
    This function uses the geodesic library to calculate the straight-line distance
    between two points, and then applies a road factor of 1.3 to account for
    the fact that roads are rarely straight lines.

    Returns:
    float: Realistic distance between the two points in km
    """
    straight_distance = geodesic((lat1, lon1), (lat2, lon2)).km
    # road factor ~1.0 (20% zyada)
    return round(straight_distance * 1.0, 2)

## Calculate distance between two points, using geodesic library and haversine formula
def calculate_distance(lat1, lon1, lat2, lon2):
    """ Uses geodesic to calculate distance in km."""
    if None in (lat1, lon1, lat2, lon2):
        return 0
    return round(geodesic((lat1, lon1), (lat2, lon2)).km, 2)

# Haversine formula version 
def calculate_distance_km(start_lat, start_lng, end_lat, end_lng):
    """ Haversine formula version"""
    R = 6371.0  # Earth radius in km
    lat1, lon1 = radians(start_lat), radians(start_lng)
    lat2, lon2 = radians(end_lat), radians(end_lng)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    return round(distance, 2)

# Auto calculate distance between two points using OSRM and geocoding if needed
def auto_calculate_distance(start_loc, end_loc, start_lat=None, start_lon=None, end_lat=None, end_lon=None):
    """
    Calculate distance between start and end points.
    - Use provided coordinates if available
    - Fallback to geocoding if coordinates are missing
    - Returns distance in KM (float)
    """
    # # Use coordinates if all provided

    if start_lat is None or start_lon is None:
        start_lat, start_lon = get_lat_lng_cached(start_loc) if start_loc else (None, None)
    if end_lat is None or end_lon is None:
        end_lat, end_lon = get_lat_lng_cached(end_loc) if end_loc else (None, None)

    # If we have coordinates, prefer OSRM for real road distance
    if None not in (start_lat, start_lon, end_lat, end_lon):
        try:
            road_km = get_road_distance_osrm(start_lat, start_lon, end_lat, end_lon)
            if road_km is not None:
                return road_km
        except Exception:
            # If OSRM fails, fallthrough to geodesic-based approximation
            return Response({"status":"error", "message": "OSRM failed to calculate distance,  falling back to geodesic approximation method to calculate distance"},
                              status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # fallback realistic estimate from straight line
        return calculate_realistic_distance(start_lat, start_lon, end_lat, end_lon)

    # If coordinates still missing, attempt text-similarity fallback
    if start_loc and end_loc:
        return estimate_distance_by_text_similarity(start_loc, end_loc)

    # Last resort
    return 0.0

# Estimate distance if geocoding fails using text similarity method 
def estimate_distance_by_text_similarity(start, end):
    """
    Estimate distance if geocoding fails
    """
    try:
        start_terms = set(start.lower().split())
        end_terms = set(end.lower().split())
        common_terms = start_terms.intersection(end_terms)
        if common_terms and len(common_terms) >= 1:
            return round(random.uniform(5, 25), 2)  # intra-city
        return round(random.uniform(50, 300), 2)  # inter-city
    except Exception:
        return round(random.uniform(50, 300), 2)

# Check if point is on route A→B
def is_point_on_route(latA, lonA, latB, lonB, latP, lonP, threshold_km=25):
    """
    Checks if a point P lies roughly on the route A→B
    """
    try:
        dist_AP = geodesic((latA, lonA), (latP, lonP)).km
        dist_PB = geodesic((latP, lonP), (latB, lonB)).km
        dist_AB = geodesic((latA, lonA), (latB, lonB)).km
        return abs((dist_AP + dist_PB) - dist_AB) <= threshold_km
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Flexible location matching using multiple strategies 
def matches_location(search_loc, carpool_loc, user_lat, user_lon, carpool_lat, carpool_lon):
    """
    Flexible location matching using multiple strategies
    """
    if not search_loc:
        return True
    
    # Text-based matching (fuzzy)
    try:
        if search_loc.lower() in carpool_loc.lower():
            return True
    except Exception:
        return False
    
    # Coordinate-based matching (20km radius)
    if user_lat and user_lon and carpool_lat and carpool_lon:
        distance = calculate_distance(user_lat, user_lon, float(carpool_lat), float(carpool_lon))
        if distance <= 20:
            return True

    #check if search terms appear in carpool location
    search_terms = search_loc.lower().split()
    carpool_text = carpool_loc.lower() if carpool_loc else ""
    
    # If any search term matches significantly
    for term in search_terms:
        if len(term) > 3 and term in carpool_text:
            return True
    
    return False

# Advanced route matching without static data 
def matches_route(search_end, carpool, user_end_lat, user_end_lon):
    """
    Advanced route matching without static data
    """
    if not search_end:
        return True
    
    # Direct destination match
    if matches_location(search_end, carpool.end_location, user_end_lat, user_end_lon, carpool.latitude_end, carpool.longitude_end):
        return True
    
    # Check if search_end is an intermediate point on the route
    if (user_end_lat and user_end_lon and 
        carpool.latitude_start and carpool.longitude_start and
        carpool.latitude_end and carpool.longitude_end):
        
        return is_point_on_route_dynamic(
            float(carpool.latitude_start), float(carpool.longitude_start),
            float(carpool.latitude_end), float(carpool.longitude_end),
            user_end_lat, user_end_lon
        )
    
    # Text-based intermediate matching
    return is_text_based_intermediate(search_end, carpool)

# Dynamic route matching using geometric calculations only 
def is_point_on_route_dynamic(latA, lonA, latB, lonB, latP, lonP, max_deviation_ratio=0.3):
    """
    Dynamic route matching using geometric calculations only
    """
    try:
        # Calculate distances
        dist_AP = geodesic((latA, lonA), (latP, lonP)).km
        dist_PB = geodesic((latP, lonP), (latB, lonB)).km
        dist_AB = geodesic((latA, lonA), (latB, lonB)).km
        
        # If point is exactly on route, AP + PB = AB
        # Allow some deviation based on route length
        max_deviation = dist_AB * max_deviation_ratio
        
        # Check if point is on route within deviatio
        return abs((dist_AP + dist_PB) - dist_AB) <= max_deviation

    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Text-based intermediate matching using static data only
def is_text_based_intermediate(search_city, carpool):
    """
    Text-based intermediate matching using static data only (less accurate), but faster to compute than dynamic route matching (geometric), and less resource-intensive than dynamic
    """
    try:

        # Add locations from current carpool route context
        route_locations = CreateCarpool.objects.filter(
            Q(start_location__icontains=carpool.start_location) | Q(end_location__icontains=carpool.end_location)
            ).values_list('start_location', 'end_location')
    
        for start, end in route_locations:
            if search_city.lower() in start.lower():
                return True
            if search_city.lower() in end.lower():
                return True
            pass
    
        # Check if search city appears in similar routes
        similar_routes = CreateCarpool.objects.filter(
            Q(start_location__icontains=carpool.start_location) |
            Q(end_location__icontains=carpool.end_location) |
            Q(start_location__icontains=search_city) |
            Q(end_location__icontains=search_city)
        )

        for route in similar_routes:
            route_locations = [route.start_location.lower(), route.end_location.lower()]
            if (search_city.lower() in route_locations and (carpool.start_location.lower() in route_locations or carpool.end_location.lower() in route_locations)):
                return True

    except CreateCarpool.DoesNotExist:
        return Response({"status":"error", "message": "Carpool does not exist"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return False