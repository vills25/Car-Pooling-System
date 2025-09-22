from django.utils import timezone
import random
from django.core.mail import send_mail
from django.conf import settings
from carpooling_app.models import Activity, Booking
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings

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
    subject = "Contact us form"
    message = f"Name: {name}\nEmail: {email}\nPhone Number: {phone_number}\nMessage: {your_message}"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = settings.DEFAULT_FROM_EMAIL
    send_mail(subject, message, from_email, [to_email])
