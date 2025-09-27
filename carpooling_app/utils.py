from django.utils import timezone
import random
from django.core.mail import send_mail
from django.conf import settings
from carpooling_app import models
from carpooling_app.models import Activity, Booking, CreateCarpool
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings
from geopy.geocoders import Nominatim
from math import atan2, radians, cos, sin, asin, sqrt
from geopy.distance import geodesic
from django.db.models import Q

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
    if isinstance(data, list):
        for km_inr in data:
            if km_inr.get("contribution_per_km"):
                km_inr["contribution_per_km"] = f"{km_inr['contribution_per_km']} INR"
            if km_inr.get("distance_km"):
                km_inr["distance_km"] = f"{km_inr['distance_km']} KM"
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
def ride_status_function(request):
    """
    This function is used to update the ride status of all bookings based on the current time.
    It loops through all bookings and checks the current time against the departure and arrival times of the carpool.
    If the booking status is "cancelled", the ride status is set to "cancelled".
    If the current time is greater than the departure time, the ride status is set to "upcoming".
    If the current time is between the departure and arrival times, the ride status is set to "active".
    If the current time is greater than or equal to the arrival time, the ride status is set to "completed".

    """
    currunt_time = timezone.now()
    bookings = Booking.objects.all()

    for booking in bookings:
        start = booking.carpool_driver_name.departure_time
        end = booking.carpool_driver_name.arrival_time

        if booking.booking_status == "cancelled":
            booking.ride_status = "cancelled"

        elif start > currunt_time:
            booking.ride_status = "upcomming"

        elif start <= currunt_time < end:
            booking.ride_status = "active"

        elif currunt_time >= end:
            booking.ride_status = "completed"

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


## get location latitude and longitude from entered string
def get_lat_lng(place_name):
    """
    Returns lat/lng for place name, else (None, None)
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
    except:
        pass
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

def calculate_realistic_distance(lat1, lon1, lat2, lon2):
    # straight-line distance
    straight_distance = geodesic((lat1, lon1), (lat2, lon2)).km
    # road factor ~1.5 (20% zyada)
    return round(straight_distance * 1.3, 2)

def calculate_distance(lat1, lon1, lat2, lon2):
    """ Uses geodesic to calculate distance in km."""
    if None in (lat1, lon1, lat2, lon2):
        return 0
    return round(geodesic((lat1, lon1), (lat2, lon2)).km, 2)

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


def auto_calculate_distance(start_loc, end_loc, start_lat=None, start_lon=None, end_lat=None, end_lon=None):
    """
    Calculate distance between start and end points.
    - Use provided coordinates if available
    - Fallback to geocoding if coordinates are missing
    - Returns distance in KM (float)
    """
    # Use coordinates if all provided
    if all([start_lat, start_lon, end_lat, end_lon]):
        return calculate_realistic_distance(start_lat, start_lon, end_lat, end_lon)
    
    # If coordinates missing, fetch from geocoding
    if start_lat is None or start_lon is None:
        start_lat, start_lon = get_lat_lng_cached(start_loc)
    if end_lat is None or end_lon is None:
        end_lat, end_lon = get_lat_lng_cached(end_loc)
    
    # If still missing, return 0
    if None in (start_lat, start_lon, end_lat, end_lon):
        return 0
    
    # Calculate realistic road distance (approx straight * 1.2)
    return calculate_realistic_distance(start_lat, start_lon, end_lat, end_lon)

def estimate_distance_by_text_similarity(start, end):
    """
    Estimate distance if geocoding fails
    """
    start_terms = set(start.lower().split())
    end_terms = set(end.lower().split())
    common_terms = start_terms.intersection(end_terms)
    if common_terms and len(common_terms) >= 1:
        return round(random.uniform(5, 25), 2)  # intra-city
    return round(random.uniform(50, 300), 2)  # inter-city

def is_point_on_route(latA, lonA, latB, lonB, latP, lonP, threshold_km=25):
    """
    Checks if a point P lies roughly on the route A→B
    """
    dist_AP = geodesic((latA, lonA), (latP, lonP)).km
    dist_PB = geodesic((latP, lonP), (latB, lonB)).km
    dist_AB = geodesic((latA, lonA), (latB, lonB)).km
    return abs((dist_AP + dist_PB) - dist_AB) <= threshold_km

def _safe_float(value, default=0.0):
    
    """
    Safely convert a value to a float, returning the default value
    if conversion fails.
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def matches_location(search_loc, carpool_loc, user_lat, user_lon, carpool_lat, carpool_lon):
    """
    Flexible location matching using multiple strategies
    """
    if not search_loc:
        return True
    
    # Text-based matching (fuzzy)
    if search_loc.lower() in carpool_loc.lower():
        return True
    
    # Coordinate-based matching (20km radius)
    if user_lat and user_lon and carpool_lat and carpool_lon:
        distance = calculate_distance(user_lat, user_lon, float(carpool_lat), float(carpool_lon))
        if distance <= 20:
            return True

    # Token-based matching (check if search terms appear in carpool location)
    search_terms = search_loc.lower().split()
    carpool_text = carpool_loc.lower()
    
    # If any search term matches significantly
    for term in search_terms:
        if len(term) > 3 and term in carpool_text:
            return True
    
    return False

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
        
        return abs((dist_AP + dist_PB) - dist_AB) <= max_deviation

    except:
        return False

def is_text_based_intermediate(search_city, carpool):
    """
    Text-based intermediate city detection using NLP-like techniques
    """
    # Get all unique locations from database to understand context
    all_locations = set()
    
    # Add locations from current carpool route context
    route_locations = CreateCarpool.objects.filter(
        Q(start_location__icontains=carpool.start_location) | Q(end_location__icontains=carpool.end_location)
        ).values_list('start_location', 'end_location')
    
    for start, end in route_locations:
        all_locations.update([start.lower(), end.lower()])
    
    # Check if search city appears in similar routes
    similar_routes = CreateCarpool.objects.filter(
        Q(start_location__icontains=carpool.start_location) |
        Q(end_location__icontains=carpool.end_location) |
        Q(start_location__icontains=search_city) |
        Q(end_location__icontains=search_city)
    )
    
    for route in similar_routes:
        route_locations = [route.start_location.lower(), route.end_location.lower()]
        if (search_city.lower() in route_locations and 
            (carpool.start_location.lower() in route_locations or 
             carpool.end_location.lower() in route_locations)):
            return True
    
    return False