from .custom_jwt_auth import IsDriverCustom, IsAuthenticatedCustom
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from .models import CreateCarpool
from .serializers import CreateCarpoolSerializer
from .user_authentication import activity
from django.db.models import Sum
from rest_framework.permissions import AllowAny

## Create Carpool (driver only)
@api_view(['POST'])
@permission_classes([IsAuthenticatedCustom])
def create_carpool(request):
    # get user
    user = request.user

    # input fields
    start_location = request.data.get('start_location')
    end_location = request.data.get('end_location')
    departure_time = request.data.get('departure_time')
    available_seats = request.data.get('available_seats')
    total_passenger_allowed = request.data.get('total_passenger_allowed')
    contribution_per_passenger = request.data.get('contribution_per_passenger', 0)
    add_note = request.data.get('add_note', '')
    arrival_time = request.data.get('arrival_time')
    contact_info = request.data.get('contact_info', '')

    # required fields
    required = ["start_location", "end_location", "departure_time", "available_seats", "total_passenger_allowed"]
    for fields in required:
        if not request.data.get(fields):
            return Response({"status":"fail","message": f"{fields} is required"}, status=status.HTTP_400_BAD_REQUEST)

    # check seats & pasanger 
    try:
        available_seats = int(available_seats)
        total_allowed = int(total_passenger_allowed)
        
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
                start_location = start_location,
                end_location = end_location,
                departure_time = departure_time,
                available_seats = available_seats,
                contribution_per_passenger = contribution_per_passenger,
                add_note = add_note,
                arrival_time = arrival_time,
                total_passenger_allowed = total_allowed,
                contact_info = contact_info
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
    get_contribution = request.data.get("contribution_per_passenger")
    get_note = request.data.get("add_note")
    get_arrival_time = request.data.get("arrival_time")
    get_total_passengers = request.data.get("total_passenger_allowed")
    get_contact = request.data.get("contact_info")

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

        if get_contribution is not None:
            carpool.contribution_per_passenger = get_contribution

        if get_note is not None:
            carpool.add_note = get_note

        if get_arrival_time is not None:
            carpool.arrival_time = get_arrival_time

        if get_contact is not None:
            carpool.contact_info = get_contact
            
        # Handle total passengers with validation
        if get_total_passengers is not None:
            try:
                carpool.total_passenger_allowed = int(get_total_passengers)
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

# Carpool list (public)
@api_view(['GET'])
@permission_classes([AllowAny])
def carpool_detail(request):
    try:
        currunt_time = timezone.now()

        queryset = CreateCarpool.objects.all()

        public_carpools = queryset.filter(departure_time__gte=currunt_time)
        
        serializer = CreateCarpoolSerializer(public_carpools, many=True, context={"request": request})
        return Response({ "status": "success", "message": "carpool details fetched", "Carpools details": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Search carpools (public) - show only upcoming rides with seats more than 0 , expired time ride hidden
@api_view(['POST'])
@permission_classes([AllowAny])
def search_carpools(request):
    currunt_time = timezone.now()
    start = request.data.get("start_location", "").strip()
    end = request.data.get("end_location", "").strip()
    date = request.data.get("date")

    try:
        qs = CreateCarpool.objects.filter(departure_time__gte=currunt_time, available_seats__gt=0)
        if start:
            qs = qs.filter(start_location__icontains=start)
        if end:
            qs = qs.filter(end_location__icontains=end)
        if date:
            qs = qs.filter(departure_time__date=date)

        if not qs.exists():
            return Response({"status":"fail","message":"No carpools found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreateCarpoolSerializer(qs, many=True)
        return Response({"status":"success","message":"Carpools fetched","Carpools": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## sort carpools by date, location, available seats, departure time, arrivval time, seats.
@api_view(['POST'])
@permission_classes([IsAuthenticatedCustom])
def sort_carpools_by(request):
    user = request.user
    try:

        queryset = CreateCarpool.objects.filter(available_seats__gt=0).order_by('-departure_time')

        start_location = request.data.get('start_location')
        end_location = request.data.get('end_location')
        available_seats = request.data.get('available_seats')
        departure_time = request.data.get('departure_time')
        arrival_time = request.data.get('arrival_time')

        if start_location:
            queryset = queryset.filter(start_location__icontains=start_location)

        if end_location:
            queryset = queryset.filter(end_location__icontains=end_location)

        if available_seats:
            try:
                seats = int(available_seats)
                queryset = queryset.filter(available_seats__gte=seats) # equal or greter then entered seats

            except:
                return Response({"status": "fail", "message": "available_seats must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        if departure_time:
            queryset = queryset.filter(departure_time__date=departure_time)

        if arrival_time:
            queryset = queryset.filter(arrival_time__date=arrival_time)

        if not queryset.exists():
            return Response({"status": "fail", "message": "No matching Carpools found"}, status=status.HTTP_404_NOT_FOUND)

        activity(user, f"{request.user.first_name} sorted Carpools")
        serializer = CreateCarpoolSerializer(queryset, many=True)

        return Response({"status": "success", "message": "Carpools fetched", "Carpools": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)