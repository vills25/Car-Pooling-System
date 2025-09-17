from operator import ge
from .user_auth import activity
from .custom_jwt_auth import IsDriverCustom, IsAuthenticatedCustom
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from .models import CreateCarpool
from .serializers import CreateCarpoolSerializer, BookingDetailSerializer
from django.db.models import Sum
from rest_framework.permissions import AllowAny

## Create Carpool (driver only)
@api_view(['POST'])
@permission_classes([IsAuthenticatedCustom])
def create_carpool(request):
    # get user
    user = request.user

    # input fields
    get_start_location = request.data.get('start_location')
    get_end_location = request.data.get('end_location')
    get_departure_time = request.data.get('departure_time')
    get_arrival_time = request.data.get('arrival_time')
    get_available_seats = request.data.get('available_seats')
    get_total_passenger_allowed = request.data.get('total_passenger_allowed')
    get_contribution_per_km = request.data.get('contribution_per_km')
    get_distance_km = request.data.get('distance_km')
    get_add_note = request.data.get('add_note', '')
    get_allow_luggage = request.data.get('allow_luggage')
    get_contact_info = request.data.get('contact_info', '')
    get_gender_preference = request.data.get('gender_preference')
    get_car_model = request.data.get('car_model')
    get_car_number = request.data.get('car_number')

    # required fields
    required = ["start_location", "end_location", "departure_time", "available_seats", "total_passenger_allowed"]
    for fields in required:
        if not request.data.get(fields):
            return Response({"status":"fail","message": f"{fields} is required"}, status=status.HTTP_400_BAD_REQUEST)

    # check seats & pasanger 
    try:
        available_seats = int(get_available_seats)
        total_allowed = int(get_total_passenger_allowed)
        
        if available_seats < 0 or total_allowed <= 0:
            return Response({"status":"fail", "message":"available_seats must be >=0 and total_passenger_allowed must be >0"}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        if available_seats > total_allowed:
            return Response({"status":"fail", "message":"available_seats cannot be greater than total_passenger_allowed"}, 
                              status=status.HTTP_400_BAD_REQUEST)
    except ValueError:
        return Response({"status":"fail", "message":"available_seats and total_passenger_allowed must be integers"}, 
                          status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            carpool = CreateCarpool.objects.create(
                carpool_creator_driver = user,
                start_location = get_start_location,
                end_location = get_end_location,
                departure_time = get_departure_time,
                arrival_time = get_arrival_time,
                available_seats = get_available_seats,
                total_passenger_allowed = get_total_passenger_allowed,
                contribution_per_km = get_contribution_per_km,
                distance_km=get_distance_km,
                add_note = get_add_note,
                allow_luggage = get_allow_luggage,
                gender_preference = get_gender_preference,
                contact_info = get_contact_info,
                car_model = get_car_model,
                car_number = get_car_number,
            )
            user_role_change = user
            if user_role_change.role != "driver":
                user_role_change.role = "driver"
                user_role_change.save()

            serializer = CreateCarpoolSerializer(carpool)
            return Response({"status":"success", "message":"Carpool added", "Carpool data": serializer.data}, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## Edit Carpool details
@api_view(['PUT'])
@permission_classes([IsDriverCustom])
def update_carpool(request):
    user = request.user
    
    # Extract all input fields
    get_carpool_id = request.data.get("createcarpool_id")
    get_available_seats = request.data.get("available_seats")
    get_start_location = request.data.get("start_location")
    get_end_location = request.data.get("end_location")
    get_departure_time = request.data.get("departure_time")
    get_arrival_time = request.data.get("arrival_time")
    get_contribution_per_km = request.data.get("contribution_per_km")
    get_distance_km = request.data.get("distance_km")
    get_add_note = request.data.get("add_note")
    get_allow_luggage = request.data.get("allow_luggage")
    get_gender_preference = request.data.get("gender_preference")
    get_contact_info = request.data.get("contact_info")
    get_car_model = request.data.get("car_model")
    get_car_number = request.data.get("car_number")
    get_total_passenger_allowed = request.data.get("get_total_passenger_allowed")

    # Validate required field
    if not get_carpool_id:
        return Response({"status":"fail","message":"createcarpool_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get the carpool to update
        carpool = CreateCarpool.objects.get(createcarpool_id=get_carpool_id)
        
        # Check ownership
        if carpool.carpool_creator_driver != user:
            return Response({"status":"fail","message":"You cannot edit other carpool details"}, status=status.HTTP_403_FORBIDDEN)

        # Handle available seats update with validation
        if get_available_seats is not None:
            try:
                new_available = int(get_available_seats)
                confirmed_count = carpool.bookings.filter(booking_status="confirmed").aggregate(total=Sum("seat_book"))["total"] or 0
                
                if new_available < confirmed_count:
                    return Response({
                        "status":"fail",
                        "message":"Available seats cannot be less than already confirmed booked seats" }, status=status.HTTP_400_BAD_REQUEST)
                
                carpool.available_seats = new_available
            except ValueError:
                return Response({"status":"fail", "message":"available_seats must be integer"}, status=status.HTTP_400_BAD_REQUEST)

        # Update other fields if provided
        if get_start_location is not None:
            carpool.start_location = get_start_location
        if get_end_location is not None:
            carpool.end_location = get_end_location
        if get_departure_time is not None:
            carpool.departure_time = get_departure_time
        if get_arrival_time is not None:
            carpool.arrival_time = get_arrival_time
        if get_contribution_per_km is not None:
            carpool.contribution_per_km = get_contribution_per_km
        if get_distance_km is not None:
            carpool.distance_km = get_distance_km
        if get_add_note is not None:
            carpool.add_note = get_add_note
        if get_allow_luggage is not None:
            carpool.allow_luggage = bool(get_allow_luggage)
        if get_gender_preference is not None:
            carpool.gender_preference = get_gender_preference
        if get_contact_info is not None:
            carpool.contact_info = get_contact_info
        if get_car_model is not None:
            carpool.car_model = get_car_model
        if get_car_number is not None:
            carpool.car_number = get_car_number
            
        # Handle total passengers with validation
        if get_total_passenger_allowed is not None:
            try:
                carpool.total_passenger_allowed = int(get_total_passenger_allowed)
            except ValueError:
                return Response({"status":"fail", "message":"total_passenger_allowed must be integer"}, status=status.HTTP_400_BAD_REQUEST)

        carpool.save()
        activity(user, f"{user.username} updated carpool {carpool.createcarpool_id}")
        serializer = CreateCarpoolSerializer(carpool, context={"request": request})

        return Response({"status":"success", "message":"Carpool updated", "data":{"carpool updated data": serializer.data} }, status=status.HTTP_200_OK)
        
    except CreateCarpool.DoesNotExist:
        return Response({"status":"fail", "message":"Carpool not found"}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
## Delete Carpool
@api_view(['DELETE'])
@permission_classes([IsDriverCustom])
def delete_carpool(request):
    user = request.user
    get_carpool_id = request.data.get("carpool_id")
    if not get_carpool_id:
        return Response({"status":"fail", "message":"carpool_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        carpool = CreateCarpool.objects.get(createcarpool_id = get_carpool_id )
        if user.role == 'admin' or carpool.carpool_creator_driver == user:
            carpool.delete()
            activity(user, f"{user.username} deleted his carpool: {get_carpool_id}")
            return Response({"status":"success", "message":"Carpool deleted"}, status=status.HTTP_200_OK)
        else:
            return Response({"status":"fail", "message":"you can not delete other's carpool"}, status=status.HTTP_401_UNAUTHORIZED)

    except CreateCarpool.DoesNotExist:
        return Response({"status":"fail", "message":"entered carpool not found!!"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
## Driver: view my carpools
@api_view(['GET'])
@permission_classes([IsDriverCustom])
def view_my_carpools(request):
    user = request.user
    # if user.role != "driver":
    #     return Response({"status":"fail","message":"only drivers can view their carpools"}, status=status.HTTP_403_FORBIDDEN)
    try:
        currunt_time = timezone.now()
        upcoming_carpool = CreateCarpool.objects.filter(carpool_creator_driver=user, departure_time__gte=currunt_time).order_by("departure_time")
        past_carpool = CreateCarpool.objects.filter(carpool_creator_driver=user, departure_time__lt=currunt_time).order_by("-departure_time")
        both_data = {
            "upcoming_carpool": CreateCarpoolSerializer(upcoming_carpool, many=True).data,
            "past_carpool": CreateCarpoolSerializer(past_carpool, many=True).data
        }
        return Response({"status":"success","message":"Carpools data fetched", "Data":{"Carpools": both_data}}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# helpers.py
def km_inr_format(data):
    """
    Add INR and KM units to contribution_per_km and distance_km.
    Works with both dict (single object) and list (multiple objects).
    """
    if isinstance(data, list):
        for c in data:
            if c.get("contribution_per_km"):
                c["contribution_per_km"] = f"{c['contribution_per_km']} INR"
            if c.get("distance_km"):
                c["distance_km"] = f"{c['distance_km']} KM"
        return data
    return data

# Carpool list (public)
@api_view(['GET'])
@permission_classes([AllowAny])
def carpool_detail(request):
    try:
        currunt_time = timezone.now()

        ## show only upcoming rides for all users
        public_carpools = CreateCarpool.objects.filter(departure_time__gte=currunt_time, available_seats__gt=0).order_by('-created_at')
        
        serializer = CreateCarpoolSerializer(public_carpools, many=True)
        return Response({ "status": "success", "message": "carpool details fetched", "Carpools details": km_inr_format(serializer.data)}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Search carpools (public) - show only upcoming rides with seats more than 0 , expired time ride hidden
@api_view(['POST'])
@permission_classes([AllowAny])
def search_carpools(request):

    start = request.data.get("start_location", "")
    end = request.data.get("end_location", "")
    date = request.data.get("date")
    luggage = request.data.get("luggage_allowed")
    gender_preference = request.data.get("gender_preference")

    try:
        qs = CreateCarpool.objects.filter(available_seats__gt=0).order_by('-departure_time')
        if start:
            qs = qs.filter(start_location__icontains=start)
        if end:
            qs = qs.filter(end_location__icontains=end)
        if date:
            qs = qs.filter(departure_time__icontains=date)
        if luggage is not None:
            qs = qs.filter(luggage_allowed = bool(luggage))
        if gender_preference:
            qs = qs.filter(gender_preference__icontains=gender_preference)
        if not qs.exists():
            return Response({"status":"fail","message":"No carpools found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreateCarpoolSerializer(qs, many=True)
        return Response({"status":"success","message":"Carpools fetched","Carpools": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## sort carpools by date, location, available seats, departure time, arrivval time, seats.
@api_view(['POST'])
@permission_classes([AllowAny])
def sort_carpools_by(request):
    user = request.user
    try:

        queryset = CreateCarpool.objects.filter(available_seats__gt=0).order_by('-departure_time')

        start_location = request.data.get('start_location')
        end_location = request.data.get('end_location')
        available_seats = request.data.get('available_seats')
        date = request.data.get('date')
        gender_preference = request.data.get('gender_preference')
        if start_location:
            queryset = queryset.filter(start_location__icontains=start_location)

        if end_location:
            queryset = queryset.filter(end_location__icontains=end_location)

        if date:
            queryset = queryset.filter(departure_time__icontains=date)

        if gender_preference:
            queryset = queryset.filter(gender_preference__icontains=gender_preference)

        if available_seats:
            try:
                seats = int(available_seats)
                queryset = queryset.filter(available_seats__gte=seats) # equal or greter then entered seats

            except:
                return Response({"status": "fail", "message": "available_seats must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        if not queryset.exists():
            return Response({"status": "fail", "message": "No matching Carpools found"}, status=status.HTTP_404_NOT_FOUND)

        activity(user, f"{request.user.first_name} sorted Carpools")
        serializer = CreateCarpoolSerializer(queryset, many=True)

        return Response({"status": "success", "message": "Carpools fetched", "Carpools": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
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