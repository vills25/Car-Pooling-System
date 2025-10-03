from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from .custom_jwt_auth import IsAdminCustom, IsAuthenticatedCustom, IsDriverOrPassengerCustom, IsDriverCustom
from .models import CreateCarpool, Booking, User, ReviewRating
from .serializers import BookingDetailSerializer, BookingSerializer, ReviewRatingSerializer
from .user_auth import activity
from .utils import auto_calculate_distance, km_inr_format, ride_status_function, send_booking_email, get_road_distance_osrm, get_lat_lng_cached
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.db.models import Avg

# Book a seat in carpool (Only Logged-in(Registered) user can book only available upcomming carpools)
@api_view(['POST'])
@permission_classes([IsDriverOrPassengerCustom, IsAdminCustom])
def book_carpool(request):
    """
    Book a seat in carpool.
    
    Parameters:
    createcarpool_id: int (required)
    seat_book: int (required, default=1)
    pickup_location: str (required)
    drop_location: str (required)
    contact_info: str (required)
    payment_mode: str (required, default="cash")
    """
    user = request.user

    get_carpool_id = request.data.get("createcarpool_id")
    if not get_carpool_id:
        return Response({"status":"fail","message":"createcarpool_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    seat_book = request.data.get("seat_book", 1)
    try:
        seat_book = int(seat_book)
        if seat_book <= 0:
            raise ValueError
    except:
        return Response({"status":"fail","message":"seat_book must be a positive integer"}, status=status.HTTP_400_BAD_REQUEST)

    pickup_location = request.data.get("pickup_location")
    drop_location = request.data.get("drop_location")
    contact_info = request.data.get("contact_info")
    payment_mode = request.data.get("payment_mode", "cash")
    # Accept optional precise coordinates if provided:
    pickup_lat = request.data.get("pickup_latitude") 
    pickup_lon = request.data.get("pickup_longitude") 
    drop_lat = request.data.get("drop_latitude")
    drop_lon = request.data.get("drop_longitude")

    distance_travelled = request.data.get("distance_travelled")
    try:
        if distance_travelled is not None and float(distance_travelled) != 0:
            distance_travelled = float(distance_travelled)
        else:
            # If precise coordinates for pickup/drop given, use them
            if pickup_lat and pickup_lon and drop_lat and drop_lon:
                try:
                    distance_travelled = get_road_distance_osrm(
                        float(pickup_lat), float(pickup_lon),
                        float(drop_lat), float(drop_lon)
                    )
                    if distance_travelled is None:
                        # fallback to old method if OSRM fails
                        distance_travelled = auto_calculate_distance(
                            pickup_location or "", drop_location or "",
                            start_lat=float(pickup_lat), start_lon=float(pickup_lon),
                            end_lat=float(drop_lat), end_lon=float(drop_lon)
                        )
                except Exception:
                    distance_travelled = 0.0

            # Else if pickup/drop text provided, estimate between those two points
            elif pickup_location and drop_location:
                try:
                    # Try OSRM using geocoded coordinates
                    start_lat, start_lon = get_lat_lng_cached(pickup_location)
                    end_lat, end_lon = get_lat_lng_cached(drop_location)
                    distance_travelled = get_road_distance_osrm(start_lat, start_lon, end_lat, end_lon)
                    if distance_travelled is None:
                        distance_travelled = auto_calculate_distance(pickup_location, drop_location)
                except Exception:
                    distance_travelled = 0.0
            else:
                try:
                    carpool_obj = CreateCarpool.objects.get(pk=get_carpool_id)
                    distance_travelled = get_road_distance_osrm(
                        carpool_obj.latitude_start, carpool_obj.longitude_start,
                        carpool_obj.latitude_end, carpool_obj.longitude_end
                    )
                    if distance_travelled is None:
                        distance_travelled = auto_calculate_distance(
                            carpool_obj.start_location,
                            carpool_obj.end_location,
                            start_lat=carpool_obj.latitude_start,
                            start_lon=carpool_obj.longitude_start,
                            end_lat=carpool_obj.latitude_end,
                            end_lon=carpool_obj.longitude_end
                        )
                except CreateCarpool.DoesNotExist:
                    distance_travelled = 0.0
                except Exception:
                    distance_travelled = 0.0
    except Exception:
        distance_travelled = 0.0

    try:
        with transaction.atomic():
            carpool = CreateCarpool.objects.get(pk=get_carpool_id)

            if carpool.departure_time < timezone.now():
                return Response({"status":"fail", "message":"This ride has already departed"}, status=status.HTTP_400_BAD_REQUEST)

            already_booked = Booking.objects.filter(carpool_driver_name=carpool, passenger_name=user, booking_status="confirmed").exists()
            if already_booked:
                return Response({"status":"fail", "message":"You already booked this carpool"}, status=status.HTTP_400_BAD_REQUEST)

            if carpool.available_seats >= seat_book:
                status_booking = "pending"
                # carpool.available_seats -= seat_book
                carpool.save()
                message = "Booking request sent to driver"
            else:
                status_booking = "waitlisted"
                message = "Ride waitlisted due to insufficient seats"

            # Create booking
            booking = Booking.objects.create(
                carpool_driver_name=carpool,
                passenger_name=user,
                seat_book=seat_book,
                distance_travelled=distance_travelled,
                payment_mode=payment_mode,
                booked_by=user,
                pickup_location=pickup_location,
                drop_location=drop_location,
                contact_info=contact_info,
                booking_status=status_booking
            )

            if user.role != "passenger":
                user.role = "passenger"
                user.save()

            activity(user, f"{user.username} {status_booking} booking {booking.booking_id} for carpool {carpool.createcarpool_id}")
            send_booking_email(booking, status_booking)

            serializer = BookingDetailSerializer(booking)
            return Response({"status":"success","message":message,"data":{"Booking Details": km_inr_format(serializer.data)}}, status=status.HTTP_201_CREATED)

    except CreateCarpool.DoesNotExist:
        return Response({"status":"fail","message":"Carpool not found"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## get booking info
@api_view(['GET'])
@permission_classes([IsDriverOrPassengerCustom, IsAdminCustom])
def my_bookings_info(request):
    """
    Fetch booking information for a user.

    Parameters:
    request (HttpRequest): Request object passed in by the Django framework.

    Returns:
    Response: A JSON response with the status, message and data of the bookings.
    The data contains two fields: "upcoming_bookings" and "past_bookings".
    The "upcoming_bookings" field contains a list of upcoming bookings for the user,
    and the "past_bookings" field contains a list of past bookings for the user.
    """
    user = request.user
    try:
        current_time = timezone.now()

        ride_status_function(request) #calling helper function for ride status
        upcoming_bookings = Booking.objects.filter(passenger_name=user, carpool_driver_name__departure_time__gte=current_time).order_by("carpool_driver_name__departure_time")
        past_bookings = Booking.objects.filter(passenger_name=user, carpool_driver_name__departure_time__lt=current_time).order_by("-carpool_driver_name__departure_time")

        data = {
            "upcoming_bookings": BookingDetailSerializer(upcoming_bookings, many=True).data,
            "past_bookings": BookingDetailSerializer(past_bookings, many=True, context={"request": request}).data
        }
        return Response({"status":"success","message":"Bookings fetched","data":{"Bookings":km_inr_format(data)}}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Update booking (change seat count or pickup/drop)
@api_view(['PUT'])
@permission_classes([IsDriverOrPassengerCustom, IsAdminCustom])
def update_my_booking(request):
    """
    Update booking information for a user.

    Parameters:
    request (HttpRequest): Request object passed in by the Django framework.
    booking_id (int): The id of the booking to update.
    seat_book (int): The new number of seats to book (optional).
    pickup_location (str): The new pickup location (optional).
    drop_location (str): The new drop off location (optional).
    contribution_amount (float): The new contribution amount (optional).

    Returns:
    Response: A JSON response with the status, message and data of the booking.
    The data contains a single field: "Booking" which is the updated booking object.
    """
    user = request.user
    data = request.data
    booking_id = data.get("booking_id")
    if not booking_id:
        return Response({"status":"fail","message":"booking_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            booking = Booking.objects.get(pk=booking_id, passenger_name=user)

            carpool = booking.carpool_driver_name
            if carpool.departure_time < timezone.now():
                return Response({"status":"fail","message":"Cannot update booking of past ride"}, status=status.HTTP_400_BAD_REQUEST)

            # If seat_book updated
            if data.get("seat_book"):
                try:
                    new_seats = int(data["seat_book"])
                except ValueError:
                    return Response({"status":"fail","message":"seat_book must be integer"}, status=status.HTTP_400_BAD_REQUEST)

                seat_diff = new_seats - booking.seat_book
                if seat_diff > 0 and carpool.available_seats < seat_diff:
                    return Response({"status":"fail","message":"Not enough seats available to increase booking"}, status=status.HTTP_400_BAD_REQUEST)

                booking.seat_book = new_seats
                carpool.available_seats -= seat_diff
                carpool.available_seats += abs(seat_diff)
                carpool.save()

            # Other fields
            booking.pickup_location = data.get("pickup_location", booking.pickup_location)
            booking.drop_location = data.get("drop_location", booking.drop_location)
            booking.contribution_amount = data.get("contribution_amount", booking.contribution_amount)

            booking.updated_by = user
            booking.save()
            activity(user, f"{user.username} updated booking {booking_id}")
            serializer = BookingDetailSerializer(booking)
            return Response({"status":"success","message":"Booking updated","data":{"Booking":serializer.data}}, status=status.HTTP_200_OK)
        
    except Booking.DoesNotExist:
        return Response({"status":"fail","message":"Booking not found"}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## cancel my bokked ride
@api_view(['DELETE'])
@permission_classes([IsDriverOrPassengerCustom, IsAdminCustom])
def cancel_booking(request):
    """
    Cancel a booking.

    Parameters:
    request (HttpRequest): Request object passed in by the Django framework.
    booking_id (int): The id of the booking to cancel.

    Returns:
    Response: A JSON response with the status, message and data of the booking.
    The data contains a single field: "Booking" which is the cancelled booking object.
    """
    user = request.user
    get_booking_id = request.data.get('booking_id')
    
    if not request.user.is_superuser and request.user != booking.passenger_name:
        return Response({"status":"fail", "message": "you can not delete others bookings"}, status=status.HTTP_403_FORBIDDEN)

    if not get_booking_id:
        return Response({"status":"fail", "message":"booking_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
       with transaction.atomic():
            booking = Booking.objects.get(pk=get_booking_id, passenger_name=user)
            if booking.booking_status == "cancelled":
                return Response({"status":"fail","message":"Booking already cancelled"}, status=status.HTTP_400_BAD_REQUEST)

            carpool = booking.carpool_driver_name
            if carpool.departure_time < timezone.now():
                return Response({"status":"fail","message":"ride has been already expired"}, status=status.HTTP_400_BAD_REQUEST)

            if booking.booking_status == "confirmed":
                carpool.available_seats += booking.seat_book
                carpool.save()

                # check for waitlisted bookings
                waitlisted = Booking.objects.filter(carpool_driver_name=carpool,booking_status="waitlisted").order_by("booked_at").first()

                if waitlisted:
                    waitlisted.booking_status = "confirmed"
                    if waitlisted.distance_travelled:
                        waitlisted.contribution_amount = carpool.contribution_per_km * waitlisted.distance_travelled
                    waitlisted.save()
                    carpool.available_seats -= waitlisted.seat_book
                    carpool.save()

            booking.booking_status = "cancelled"
            booking.save()

            activity(user, f"{user.username} cancelled booking {get_booking_id}")
            return Response({"status":"success", "message":"Booking cancelled"}, status=status.HTTP_200_OK)
       
    except Booking.DoesNotExist:
        return Response({"status":"fail","message":"Booking not found"}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## sort/filter for user of his booking , like sort according to time, date, etc...
@api_view(['POST'])
@permission_classes([IsDriverOrPassengerCustom, IsAdminCustom])
def filter_bookings(request):
    """
    Filter and sort bookings made by a user.

    Parameters:
    filter_by (str): Filter bookings by "upcoming" or "past".
    sort_by (str): Sort bookings by "latest_ride_date" or "earliest_ride_date".

    Returns:
    Response: A JSON response with the status, message and data of the filtered and sorted bookings.
    The data contains a single field: "Bookings" which is a list of booking objects.
    """
    user = request.user
    filter_by = request.data.get("filter_by")
    sort_by = request.data.get("sort_by")

    try:
        bookings = Booking.objects.filter(passenger_name=user)

        if filter_by == "upcoming":
            bookings = bookings.filter(carpool_driver_name__departure_time__gte=timezone.now())
        elif filter_by == "past":
            bookings = bookings.filter(carpool_driver_name__departure_time__lt=timezone.now())

        if sort_by == "latest_ride_date":
            bookings = bookings.order_by("carpool_driver_name__departure_time")
        elif sort_by == "earliest_ride_date":
            bookings = bookings.order_by("carpool_driver_name__departure_time")

        serializer = BookingDetailSerializer(bookings, many=True)
        return Response({"status":"success","message":"Filtered and sorted bookings fetched","data":{"Bookings":serializer.data}}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#-------- DRIVER ONLY --------#

## booking request from passenger view for driver role.
@api_view(['GET'])
@permission_classes([IsDriverCustom, IsAdminCustom])
def driver_view_booking_requests(request):
    """
    Returns a list of all pending booking requests for a driver.

    Parameters:
    request (HttpRequest): Request object passed in by the Django framework.

    Returns:
    Response: A JSON response with the status, message and data of the pending booking requests.
    The data contains a single field: "Requests" which is a list of booking objects.
    """
    driver = request.user
    try:
        bookings = Booking.objects.filter(carpool_driver_name__carpool_creator_driver=driver,booking_status="pending").order_by("booked_at")

        if not bookings.exists():
            return Response({"status": "fail", "message": "No pending booking requests"}, status=status.HTTP_404_NOT_FOUND)

        serializer = BookingDetailSerializer(bookings, many=True)
        return Response({"status": "success", "data":{"Requests": serializer.data}}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## Approve/Reject booking request from passenger view for driver role.
@api_view(['PUT'])
@permission_classes([IsDriverCustom, IsAdminCustom])
def driver_approve_reject_booking(request):
    """
    Approve or reject a booking request from a passenger.

    Parameters:
    booking_id (int): The id of the booking to approve or reject.
    action (str): The action to take on the booking - "approve" or "reject".

    Returns:
    Response: A JSON response with the status, message and data of the booking.
    The data contains a single field: "Booking" which is the updated booking object.
    """
    driver = request.user
    get_booking_id = request.data.get("booking_id")
    get_action = request.data.get("action")

    if not get_booking_id or not get_action:
        return Response({"status": "fail", "message": "booking_id and action required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        booking = Booking.objects.get(booking_id = get_booking_id, carpool_driver_name__carpool_creator_driver = driver)

        if booking.booking_status != "pending":
            return Response({"status":"fail", "message":"booking already in progress"}, status=status.HTTP_400_BAD_REQUEST)
        
        carpool = booking.carpool_driver_name
        with transaction.atomic():
            if get_action == "approve":
                if carpool.available_seats < booking.seat_book:
                    booking.booking_status = "waitlisted"
                    booking.save()
                    send_booking_email(booking, "waitlisted")
                    return Response({"status":"fail", "message":"Not enough seat! your seats is curruntly in waiting list."}, status=status.HTTP_400_BAD_REQUEST)
                if booking.distance_travelled:
                    booking.contribution_amount = carpool.contribution_per_km * booking.distance_travelled

                booking.booking_status = "confirmed"
                booking.save()

                carpool.available_seats -= booking.seat_book
                carpool.save()

                send_booking_email(booking, "confirmed")
                activity(driver, f"Driver{driver.username} aproved booking {booking.booking_id}")
                serializer = BookingDetailSerializer(booking)
                return Response({"status":"success","message":"Booking approved","data":{"Booking":serializer.data}}, status=status.HTTP_200_OK)

            elif get_action == "reject":
                booking.booking_status = "rejected"
                booking.save()
                send_booking_email(booking, "rejected")
                activity(driver, f"Driver {driver.username} rejected booking {booking.booking_id}")
                return Response({"status": "success", "message": "Booking Rejected"}, status=status.HTTP_200_OK)

            else:
                return Response({"status": "fail", "message": "Invalid action. please use approve or reject"}, status=status.HTTP_400_BAD_REQUEST)

    except Booking.DoesNotExist:
        return Response({"status": "fail", "message": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
## view each confirmed booking passenger for each carpool
@api_view(['GET'])
@permission_classes([IsDriverCustom, IsAdminCustom])
def view_booked_passenger(request):
    """
    Returns a list of confirmed bookings for all carpools created by the requesting user (driver).
    The list is sorted in descending order of booking time.
    Only accessible to driver users.
    """
    user = request.user
    
    try:
        carpools = CreateCarpool.objects.filter(carpool_creator_driver=user).order_by("-created_at")
        
        if not carpools.exists():
            return Response({"status":"fail","message":"You have no carpools"}, status=status.HTTP_404_NOT_FOUND)

        all_confirmed_bookings = []
        for carpool in carpools:
            confirmed_bookings = carpool.bookings.filter(booking_status="confirmed").order_by("booked_at")

            if confirmed_bookings.exists():
                serializer = BookingDetailSerializer(confirmed_bookings, many=True)
                all_confirmed_bookings.extend(serializer.data)

        if not all_confirmed_bookings:
            return Response({"status":"fail","message":"No confirmed bookings found for your carpools"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"status":"success", "message":"Confirmed bookings fetched", "data":{"confirmed bookings": all_confirmed_bookings}}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## send email to passanger when ride is about to start before 40 minutes, if no journey is scheduled then return response as no upcoming rides.
@api_view(['GET'])
@permission_classes([IsDriverCustom, IsAdminCustom])
def ride_reminder_notifications(request):
    """
      -  Send ride reminders to passengers 40 minutes before their scheduled departure time.
      -  Only upcoming rides scheduled by the driver (logged in user) will be considered.
      -  If no upcoming rides are found, a response with status "fail" and message "No upcoming rides found" will be returned.
      -  If there are upcoming rides, a response with status "success" and message "Ride reminders sent successfully" will be returned.
      -  The response will also contain a list of upcoming bookings in the data field.

        Example:
        {
            "status": "success",
            "message": "Ride reminders sent successfully",
            "data": [
                {
                    "booking_id": ...,
                    "passenger_name": ...,
                    "carpool_driver_name": ...,
                    "departure_time": ...,
                }
            ]
        }
    """
    user = request.user
    try:
        current_time =timezone.now()
        print("##### Current Time >>>", current_time)

        future_bookings = Booking.objects.filter(carpool_driver_name__carpool_creator_driver=user,booking_status__iexact="confirmed",
                                        carpool_driver_name__departure_time__gt=current_time).select_related("carpool_driver_name").order_by("carpool_driver_name__departure_time")

        print("##### future_bookings >>>", future_bookings)

        upcoming_bookings = []

        for booking in future_bookings:
            print("##### booking >>>", booking)
            carpool = booking.carpool_driver_name
            time_diff = (carpool.departure_time - current_time).total_seconds() / 60

            if 0 <= time_diff <= 40:   # only future rides within 40 min
                upcoming_bookings.append(booking)
                print("##### upcoming >>>", upcoming_bookings)

        if upcoming_bookings:
            for booking in upcoming_bookings:
                carpool = booking.carpool_driver_name
                if booking.passenger_name.email:
                    subject = f"🚗 Ride Reminder: Your Trip Starts at {carpool.departure_time.strftime('%I:%M %p')}"

                    html_message = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <h2 style="color: #2E86C1;">🚗 Ride Reminder</h2>
                        <p>Hello <b>{booking.passenger_name.username}</b>,</p>
                        
                        <p>This is a friendly reminder for your upcoming ride:</p>
                        
                        <table style="border-collapse: collapse; margin: 10px 0;">
                        <tr>
                            <td style="padding: 8px; font-weight: bold; color: #27AE60;">🟢 Pickup Location:</td>
                            <td style="padding: 8px;">{booking.pickup_location or carpool.start_location}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold; color: #E74C3C;">🔴 Drop Location:</td>
                            <td style="padding: 8px;">{booking.drop_location or carpool.end_location}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold; color: #8E44AD;">🕒 Departure Time:</td>
                            <td style="padding: 8px;">{carpool.departure_time.strftime('%I:%M %p')}</td>
                        </tr>
                        </table>
                        
                        <p style="background: #FFF3CD; padding: 10px; border-left: 4px solid #FFC107;">
                        <b>⚠ Please be ready at least 5–10 minutes before departure.</b>
                        </p>
                        
                        <p>Thank you for choosing <b>Carpool</b>!<br>
                        Safe travels 🚀</p>
                        
                        <p style="color: #888; font-size: 12px;">— The Carpool Team</p>
                    </body>
                    </html>
                    """

                    # Plain text fallback (in case HTML not supported)
                    text_message = strip_tags(html_message)

                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=text_message,
                        from_email="noreply@carpool.com",
                        to=[booking.passenger_name.email]
                    )
                    email.attach_alternative(html_message, "text/html")
                    email.send()

            serializer = BookingSerializer(upcoming_bookings, many=True)
            return Response({"status": "success", "message": "Ride reminders sent successfully", "data": serializer.data}, status=status.HTTP_200_OK)

        next_booking = future_bookings.first()
        if not next_booking:
            return Response({"status": "fail", "message": "No upcoming rides found"}, status=status.HTTP_404_NOT_FOUND)

        carpool = next_booking.carpool_driver_name
        time_diff = int((carpool.departure_time - current_time).total_seconds() / 60)
        return Response({"status": "info", "message": f"Your next ride starts at {carpool.departure_time.strftime('%I:%M %p')} (in {time_diff} minutes)"}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## give review
@api_view(["POST"])
@permission_classes([IsAuthenticatedCustom])
def give_review_rating(request):
    """
    Add review for a driver (review_given_by = request.user)
    Expect JSON or form-data:
    {
      "review_for_username": "Mahesh",
      "carpool_id": 1,
      "booking_id": 3,
      "rating": 5,
      "comment": "Nice ride!"
    }
    """
    user = request.user
    get_review_given_to_name = request.data.get("review_given_to_name")
    get_carpool_id = request.data.get("carpool_id")
    get_booking_id = request.data.get("booking_id")
    get_rating = request.data.get("rating")
    get_comment = request.data.get("comment")

    # Required fields check
    for key in ["review_for_username", "carpool_id", "booking_id", "rating"]:
        if key not in request.data:
            return Response({"status":"fail","message": f"'{key}' is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        review_for = User.objects.get(username = get_review_given_to_name)
        carpool = CreateCarpool.objects.get(createcarpool_id = get_carpool_id)
        booking = Booking.objects.get(booking_id = get_booking_id)

        # reviewer must be passenger of the booking
        if booking.passenger_name != user:
            return Response({"status":"fail","message": "You can only review if you are the passenger for this booking"}, status=status.HTTP_403_FORBIDDEN)

        # booking must belong to carpool
        if booking.carpool_driver_name != carpool:
            return Response({"status":"fail","message": "Booking does not belong to this carpool"}, status=status.HTTP_400_BAD_REQUEST)

        # carpool driver must match review_for
        if carpool.carpool_creator_driver != review_for:
            return Response({"status":"fail","message": "'review_for_username' is not the driver of this carpool"}, status=status.HTTP_400_BAD_REQUEST)

        # Rating validation
        try:
            rating = int(get_rating)
            if rating < 1 or rating > 5:
                return Response({"status":"fail","message": "rating must be between 1 and 5"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({"status":"fail","message": "rating must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
        # Create review
        review = ReviewRating.objects.create(
            review_given_by=user,
            review_for=review_for,
            carpool=carpool,
            booking=booking,
            rating=rating,
            comment=get_comment
        )

        serializer = ReviewRatingSerializer(review)
        return Response({"status":"success","message": "Review added successfully", "data": serializer.data}, status=status.HTTP_201_CREATED)
    
    except Booking.DoesNotExist:
        return Response({"status":"fail","message": "booking not found"}, status=status.HTTP_400_BAD_REQUEST)

    except CreateCarpool.DoesNotExist:
        return Response({"status":"fail","message": "carpool not found"}, status=status.HTTP_400_BAD_REQUEST)

    except User.DoesNotExist:
        return Response({"status":"fail","message": "review_for user not found"}, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## view driver info
@api_view(["POST"])
@permission_classes([IsAuthenticatedCustom])
def view_driver_info(request):
    """
    Get driver info + stats + reviews
    Response:
    - driver_info: first_name, email, phone_number, address
    - total_carpools
    - total_reviews
    - average_rating
    """
    get_driver_user_id = request.data.get("driver_user_id")
    try:
        get_driver = User.objects.get(user_id=get_driver_user_id)

        driver_data = {
            "first_name": get_driver.first_name,
            "email": get_driver.email,
            "phone_number": getattr(get_driver, "phone_number", None),
            "address": getattr(get_driver, "address", None)
        }

        total_carpools = CreateCarpool.objects.filter(carpool_creator_driver=get_driver).count()

        reviews_queryset = ReviewRating.objects.filter(review_for=get_driver).order_by("-created_at")
        total_reviews = reviews_queryset.count()
        avg_rating = reviews_queryset.aggregate(Avg("rating"))["rating__avg"] or 0
        avg_rating = round(float(avg_rating), 2) if total_reviews else 0

        reviews_data = []
        for review in reviews_queryset[:5]:
            reviews_data.append({
                "review_id": review.review_id,
                "reviewer_name": review.review_given_by.username,
                "rating": review.rating,
                "comment": review.comment,
                "created_at": review.created_at
            })

        response_data = {
            "driver_info": driver_data,
            "total_carpools": total_carpools,
            "total_reviews": total_reviews,
            "average_rating": avg_rating,
            "recent_reviews": reviews_data
        }

        return Response({"status":"success", "message": "Driver info fetched", "data": response_data}, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({"status":"fail", "message": "driver not found"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"status":"fail", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
