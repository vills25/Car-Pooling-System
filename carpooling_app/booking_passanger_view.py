from .custom_jwt_auth import IsDriverOrPassengerCustom
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from .models import CreateCarpool, Booking
from .serializers import BookingDetailSerializer
from .user_authentication import activity

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

# Book a seat in carpool
@api_view(['POST'])
@permission_classes([IsDriverOrPassengerCustom])
def book_carpool(request):
    user = request.user

    get_carpool_id = request.data.get("createcarpool_id")
    seats = request.data.get("seat_book", 1)
    get_contribution_amount = request.data.get("contribution_amount", 0)
    get_pickup_location = request.data.get("pickup_location")
    get_drop_location = request.data.get("drop_location")
    get_contact_info = request.data.get("contact_info")

    if not get_carpool_id:
        return Response({"status":"fail","message":"createcarpool_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    seats = int(seats)
    if seats <= 0 or not int:
        return Response({"status":"fail","message":"seat_book must be positive or integer"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        with transaction.atomic():
            carpool = CreateCarpool.objects.get(pk=get_carpool_id)

            # Past ride check
            if carpool.departure_time < timezone.now():
                return Response({"status":"fail", "message":"this ride has been expired"}, status=status.HTTP_400_BAD_REQUEST)

            # Seat availability check
            if carpool.available_seats < seats:
                return Response({"status":"fail", "message":"this ride is full"}, status=status.HTTP_400_BAD_REQUEST)

            # Prevent double booking
            if Booking.objects.filter(carpool_driver_name=carpool, passenger_name=user, booking_status="confirmed").exists():
                return Response({"status":"fail", "message":"you already booked this carpool"}, status=status.HTTP_400_BAD_REQUEST)

            booking = Booking.objects.create(
                carpool_driver_name = carpool,
                passenger_name = user,
                seat_book = seats,
                contribution_amount = get_contribution_amount,
                booked_by = user,
                pickup_location = get_pickup_location,
                drop_location = get_drop_location,
                contact_info = get_contact_info,
                booking_status = "confirmed"
            )
            
            carpool.available_seats -= seats
            carpool.save()
            
            user_role_change = user
            if user_role_change.role != "passenger":
                user_role_change.role = "passenger"
                user_role_change.save()

            activity(user, f"{user.username} booked {seats} seat(s) in carpool {carpool.createcarpool_id}")

            serializer = BookingDetailSerializer(booking, context={'request': request})
            return Response({"status":"success","message":"Ride Book successful","Booking Details":serializer.data}, status=status.HTTP_201_CREATED)

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
        currunt_time = timezone.now()

        ride_status_function(request) #calling helper function for ride status

        upcoming_bookings = Booking.objects.filter(passenger_name=user, carpool_driver_name__departure_time__gte=currunt_time).order_by("carpool_driver_name__departure_time")
        past_bookings = Booking.objects.filter(passenger_name=user, carpool_driver_name__departure_time__lt=currunt_time).order_by("-carpool_driver_name__departure_time")

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

            booking.booking_status = "cancelled"
            booking.save()
            carpool.available_seats += booking.seat_book
            carpool.save()

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