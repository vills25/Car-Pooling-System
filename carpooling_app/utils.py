from django.utils import timezone
import random
from django.core.mail import send_mail
from django.conf import settings
from carpooling_app.models import Activity, Booking

def user_is_admin(user):
    return user.role == "admin" or getattr(user, "is_superuser", False)

## Save activity log
def activity(user, details):
    try:
        Activity.objects.create(user=user, details=details)
    except Exception as e:
        print("Activity log failed:", str(e))

## Generate random OTP (6 digit)
def generate_otp():
    return str(random.randint(100000, 999999))

## Send OTP email
def send_otp_email(email, otp):
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
    message = ""
    passenger_email = booking.passenger_name.email
    carpool = booking.carpool_driver_name

    if status_type == "confirmed":
        subject = "Carpool Booking Confirmed"
        message = (
            f"Hello {booking.passenger_name.first_name},\n\n"
            f"Your Booking ID: {booking.booking_id} has been confirmed.\n\n"
            f"Journey From: {carpool.start_location} To {carpool.end_location}\n"
            f"Departure time: {carpool.departure_time}\nSeats booked: {booking.seat_book}\n"
            f"Total fare price: {booking.contribution_amount} INR\n\n Happy Journey!\n\nCustomer Helpline: 1800-000-000 or +91 9856896548"
        )
    elif status_type == "rejected":
        subject = "Carpool Booking Rejected"
        message = f"Hello {booking.passenger_name.first_name},\n\nYour Booking ID: {booking.booking_id} was rejected by the driver."

    elif status_type == "waitlisted":
        subject = "Carpool Booking Waitlisted"
        message = f"Hello {booking.passenger_name.first_name},\n\nYour Booking ID: {booking.booking_id} is waitlisted due to no available seats.\n We will get back to you shortly or you can cancle and find another available ride.\n\n Customer Helpline: 1800-000-000 or +91 9856896548"

    elif status_type == "cancelled":
        subject = "Carpool Booking Cancelled"
        message = f"Hello {booking.passenger_name.first_name},\n\nYour Booking ID: {booking.booking_id} has been cancelled.\n Carpool Management System,\n Customer Helpline: 1800-000-000 or +91 9856896548"
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [passenger_email])
    except Exception as e:
        print("Email send failed:", e)

## Helper function for Ride status 
def ride_status_function(request):
    currunt_time = timezone.localtime(timezone.now())
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