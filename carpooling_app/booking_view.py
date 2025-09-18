from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from .custom_jwt_auth import IsDriverOrPassengerCustom, IsDriverCustom
from .models import CreateCarpool, Booking
from .serializers import BookingDetailSerializer
from .user_auth import activity
from .utils import ride_status_function, send_booking_email

# Book a seat in carpool (Only Logged-in(Registered) user can book only available upcomming carpools)
@api_view(['POST'])
@permission_classes([IsDriverOrPassengerCustom])
def book_carpool(request):
    user = request.user

    get_carpool_id = request.data.get("createcarpool_id")
    get_seats = request.data.get("seat_book", 1)
    get_pickup_location = request.data.get("pickup_location")
    get_drop_location = request.data.get("drop_location")
    get_contact_info = request.data.get("contact_info")
    get_distance_travelled=float(request.data.get("distance_travelled", 0))
    get_payment_mode=request.data.get("payment_mode", "cash")

    if not get_carpool_id:
        return Response({"status":"fail","message":"createcarpool_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    seat_book = int(get_seats)
    if seat_book <= 0 or not int:
        return Response({"status":"fail","message":"seat_book must be positive or integer"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        with transaction.atomic():
            carpool = CreateCarpool.objects.get(pk=get_carpool_id)

            # Past ride check
            if carpool.departure_time < timezone.now():
                return Response({"status":"fail", "message":"this ride has been expired"}, status=status.HTTP_400_BAD_REQUEST)

            # Seat availability check
            if carpool.available_seats < seat_book:
                return Response({"status":"fail", "message":"this ride is full"}, status=status.HTTP_400_BAD_REQUEST)

            # Prevent double booking
            if Booking.objects.filter(carpool_driver_name=carpool, passenger_name=user, booking_status="confirmed").exists():
                return Response({"status":"fail", "message":"you already booked this carpool"}, status=status.HTTP_400_BAD_REQUEST)

             # If no seats currently available -> create waitlisted booking
            if carpool.available_seats < seat_book:
                booking = Booking.objects.create(
                    carpool_driver_name = carpool,
                    passenger_name = user,
                    seat_book = seat_book,
                    distance_travelled = get_distance_travelled,
                    payment_mode = get_payment_mode,
                    booked_by = user,
                    pickup_location = get_pickup_location,
                    drop_location = get_drop_location,
                    contact_info = get_contact_info,
                    booking_status = "waitlisted"
                )
                activity(user, f"{user.username} waitlisted booking {booking.booking_id} for carpool {carpool.createcarpool_id}")
                send_booking_email(booking, "waitlisted")
                serializer = BookingDetailSerializer(booking, context={'request': request})
                return Response({"status":"success","message":"Ride waitlisted","Booking Details":serializer.data}, status=status.HTTP_201_CREATED)

            booking = Booking.objects.create(
                carpool_driver_name=carpool,
                passenger_name=user,
                seat_book=seat_book,
                distance_travelled=get_distance_travelled,
                payment_mode=get_payment_mode,
                booked_by=user,
                pickup_location=get_pickup_location,
                drop_location=get_drop_location,
                contact_info=get_contact_info,
                booking_status="pending"
            )

            carpool.available_seats -= seat_book
            carpool.save()
            
            user_role_change = user
            if user_role_change.role != "passenger":
                user_role_change.role = "passenger"
                user_role_change.save()

            activity(user, f"{user.username} requested booking {booking.booking_id} for carpool {carpool.createcarpool_id}")
            serializer = BookingDetailSerializer(booking, context={'request': request})
            return Response({"status":"success","message":"Booking request sent to driver","Booking Details":serializer.data}, status=status.HTTP_201_CREATED)

    except CreateCarpool.DoesNotExist:
        return Response({"status":"fail","message":"Carpool not found"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## get booking info
@api_view(['GET'])
@permission_classes([IsDriverOrPassengerCustom])
def my_bookings_info(request):
    user = request.user
    try:
        current_time = timezone.localtime(timezone.now())
        print("####### CURRUNT TIME >>>>>>>>>>>>>>>>>>>", current_time)
        ride_status_function(request) #calling helper function for ride status
        upcoming_bookings = Booking.objects.filter(passenger_name=user, carpool_driver_name__departure_time__gte=current_time).order_by("carpool_driver_name__departure_time")
        past_bookings = Booking.objects.filter(passenger_name=user, carpool_driver_name__departure_time__lt=current_time).order_by("-carpool_driver_name__departure_time")

        data = {
            "upcoming_bookings": BookingDetailSerializer(upcoming_bookings, many=True, context={"request": request}).data,
            "past_bookings": BookingDetailSerializer(past_bookings, many=True, context={"request": request}).data
        }
        return Response({"status":"success","message":"Bookings fetched","Bookings":data}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Update booking (change seat count or pickup/drop)
@api_view(['PUT'])
@permission_classes([IsDriverOrPassengerCustom])
def update_my_booking(request):
    user = request.user
    data = request.data
    booking_id = data.get("booking_id")
    if not booking_id:
        return Response({"status":"fail","message":"booking_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            booking = Booking.objects.get(pk=booking_id, passenger_name=user)

            # if booking.booking_status != "confirmed":
            #     return Response({"status":"fail","message":"only confirmed bookings can be updated"}, status=status.HTTP_400_BAD_REQUEST)

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
                carpool.save()

            # Other fields
            booking.pickup_location = data.get("pickup_location", booking.pickup_location)
            booking.drop_location = data.get("drop_location", booking.drop_location)
            booking.contribution_amount = data.get("contribution_amount", booking.contribution_amount)

            booking.save()
            activity(user, f"{user.username} updated booking {booking_id}")
            serializer = BookingDetailSerializer(booking, context={"request": request})
            return Response({"status":"success","message":"Booking updated","Booking":serializer.data}, status=status.HTTP_200_OK)
        
    except Booking.DoesNotExist:
        return Response({"status":"fail","message":"Booking not found"}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## cancel my bokked ride
@api_view(['DELETE'])
@permission_classes([IsDriverOrPassengerCustom])
def cancel_booking(request):
    user = request.user
    get_booking_id = request.data.get('booking_id')
    
    if not request.user.is_superuser and request.user:
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
@permission_classes([IsDriverOrPassengerCustom])
def filter_bookings(request):
    user = request.user
    filter_by = request.data.get("filter_by")
    sort_by = request.data.get("sort_by")

    bookings = Booking.objects.filter(passenger_name=user)

    if filter_by == "upcoming":
        bookings = bookings.filter(carpool_driver_name__departure_time__gte=timezone.now())
    elif filter_by == "past":
        bookings = bookings.filter(carpool_driver_name__departure_time__lt=timezone.now())

    if sort_by == "latest_ride_date":
        bookings = bookings.order_by("carpool_driver_name__departure_time")
    elif sort_by == "earliest_ride_date":
        bookings = bookings.order_by("-carpool_driver_name__departure_time")

    serializer = BookingDetailSerializer(bookings, many=True, context={"request": request})
    return Response({"status":"success","message":"Filtered and sorted bookings fetched","Bookings":serializer.data}, status=status.HTTP_200_OK)

#-------- DRIVER ONLY --------#

## booking request from passenger view for driver role.
@api_view(['GET'])
@permission_classes([IsDriverCustom])
def driver_view_booking_requests(request):
    driver = request.user
    try:
        bookings = Booking.objects.filter(carpool_driver_name__carpool_creator_driver=driver,booking_status="pending").order_by("booked_at")

        if not bookings.exists():
            return Response({"status": "fail", "message": "No pending booking requests"}, status=status.HTTP_404_NOT_FOUND)

        serializer = BookingDetailSerializer(bookings, many=True, context={"request": request})
        return Response({"status": "success", "Requests": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## Approve/Reject booking request from passenger view for driver role.
@api_view(['PUT'])
@permission_classes([IsDriverCustom])
def driver_approve_reject_booking(request):
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
                return Response({"status":"success","message":"Booking approved","Booking":serializer.data}, status=status.HTTP_200_OK)

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
@permission_classes([IsDriverCustom])
def view_booked_passenger(request):
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

        return Response({"status":"success", "message":"Confirmed bookings fetched", "Data":{"confirmed bookings": all_confirmed_bookings}}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)