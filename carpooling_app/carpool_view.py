from datetime import timedelta
from .user_auth import activity
from .utils import km_inr_format
from .models import CreateCarpool
from .serializers import CreateCarpoolSerializer
from .custom_jwt_auth import IsDriverCustom, IsAuthenticatedCustom, IsDriverOrPassengerCustom
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from rest_framework.permissions import AllowAny

#-------- PUBLIC (Anyone can see this details) --------#

# Carpool list (public)
@api_view(['GET'])
@permission_classes([AllowAny])
def carpool_detail(request):
    """
    This API will fetch the details of all the public carpools created by drivers.
    It will only show the upcoming carpools with available seats more than 0.
    The carpools will be sorted in descending order of departure time.
    - Returns a JSON response with the status, message and data of the public carpools.
    - The data will contain the details of the carpools in the following format: 
        {
            "Carpools details": [
                {
                    "createcarpool_id": ...,
                    "carpool_creator_driver": ...,
                    "start_location": ...,
                    "end_location": ...,
                    "departure_time": ...,
                    "available_seats": ...,
                }
            ]
        }
    - If there are no public carpools available, it will return a 404 status code with a message "No carpools found".
    """
    try:
        current_time = timezone.now()
        public_carpools = CreateCarpool.objects.filter(departure_time__gte=current_time, available_seats__gt=0).order_by('-created_at')

        serializer = CreateCarpoolSerializer(public_carpools, many=True)
        return Response({ "status": "success", "message": "carpool details fetched", "data":{"Carpools details": km_inr_format(serializer.data)}}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Search carpools (public) - show only upcoming rides with seats more than 0 , expired time ride hidden
@api_view(['POST'])
@permission_classes([AllowAny])
def search_carpools(request):

    """
    Search carpools based on start location, end location and date.
    
    Parameters:
    start_location (string): The start location of the carpools.
    end_location (string): The end location of the carpools.
    date (string): The date on which the carpools are available.
    
    Returns:
    Response: A JSON response with the status, message and data of the searched carpools.
    If there are no carpools found, it will return a 404 status code with a message "No carpools found".
    """
    start = request.data.get("start_location")
    end = request.data.get("end_location")
    date = request.data.get("date")
    try:
        qs = CreateCarpool.objects.filter(available_seats__gt=0).order_by('-departure_time')
        if start:
            qs = qs.filter(start_location__icontains=start)

        if end:
            qs = qs.filter(end_location__icontains=end)

        if date:
            qs = qs.filter(departure_time__icontains=date)

        if not qs.exists():
            return Response({"status":"fail","message":"No carpools found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreateCarpoolSerializer(qs, many=True)
        return Response({"status":"success","message":"Carpools fetched","data":{"Carpools": km_inr_format(serializer.data)}}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## sort carpools by date, location, available seats, departure time, arrivval time, seats.
@api_view(['POST'])
@permission_classes([AllowAny])
def sort_carpools_by(request):
    """
    Sort carpools based on the given parameters.

    Parameters:
    start_location (string): The start location of the carpools.
    end_location (string): The end location of the carpools.
    date (string): The date on which the carpools are available.
    available_seats (integer): The minimum number of available seats in the carpools.
    gender_preference (string): The preferred gender of the driver.
    luggage (boolean): Whether luggage is allowed or not.

    Returns:
    Response: A JSON response with the status, message and data of the sorted carpools.
    If there are no carpools found, it will return a 404 status code with a message "No matching Carpools found".
    """
    user = request.user
    try:

        queryset = CreateCarpool.objects.filter(available_seats__gt=0).order_by('-departure_time')

        start_location = request.data.get('star_location')
        end_location = request.data.get('end_loctation')
        date = request.data.get('date')
        available_seats = request.data.get('available_seats')
        gender_preference = request.data.get('gender_preference')
        luggage = request.data.get("luggage_allowed")
        
        if start_location:
            queryset = queryset.filter(start_location__icontains=start_location)

        if end_location:
            queryset = queryset.filter(end_location__icontains=end_location)

        if date:
            queryset = queryset.filter(departure_time__icontains=date)

        if luggage is not None:
            luggage_bool = str(luggage).lower() == "true"
            queryset = queryset.filter(allow_luggage=luggage_bool)  

        if gender_preference:
            queryset = queryset.filter(gender_preference__iexact=gender_preference)

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

        return Response({"status": "success", "message": "Carpools fetched", "data":{"Carpools": km_inr_format(serializer.data)}}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


#-------- CARPOOL CRUD --------#

## Create Carpool (Anyone authenticated user can book carpool)
@api_view(['POST'])
@permission_classes([IsAuthenticatedCustom])
def create_carpool(request):
    """
    Create a new carpool by driver.

    Parameters:
    start_location (str): required, starting location of the carpool
    end_location (str): required, ending location of the carpool
    departure_time (datetime): required, departure time of the carpool
    arrival_time (datetime): required, arrival time of the carpool
    available_seats (int): required, number of available seats in the carpool
    total_passenger_allowed (int): required, total number of passengers allowed in the carpool
    contribution_per_km (float): required, contribution per km in the carpool
    distance_km (float): required, distance of the carpool in km
    add_note (str): optional, additional information about the carpool
    allow_luggage (bool): optional, whether the carpool allows luggage
    gender_preference (str): optional, gender preference of the carpool
    contact_info (str): optional, contact information of the carpool
    car_model (str): optional, car model of the carpool
    car_number (str): optional, car number of the carpool

    Returns:
    Response: a json response with the status, message and the carpool data
    """
    user = request.user
    
    current_time = timezone.now()
    two_hours_ahead = current_time + timedelta(hours=1)

    ## check if user already has an active or upcoming journey
    check_upcoming_journey = CreateCarpool.objects.filter(carpool_creator_driver=user, departure_time__lte=two_hours_ahead, arrival_time__gte=current_time).exists()

    if check_upcoming_journey:
        return Response(
            {"status": "fail", "message": "You already have an active or upcoming journey within 1 hour. Cannot create new journey."},status=status.HTTP_400_BAD_REQUEST)

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
            activity(user, f"{user.username} created a new carpool {carpool.createcarpool_id} and assigned driver role")
            serializer = CreateCarpoolSerializer(carpool)
            return Response({"status":"success", "message":"Carpool added", "data":{"Carpool data": serializer.data}}, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## user who created carpool will assigned driver role and only he can with driver role UPDATE/DELETE/VIEW his carpool details.
## Edit Carpool details 
@api_view(['PUT'])
@permission_classes([IsDriverCustom])
def update_carpool(request):
    """
    Update the details of a carpool created by the user.

    This API will update the details of a carpool created by the user.
    It will only update the details of the carpool if the user is the creator of the carpool.
    It will also validate the input fields and return an error if any of the fields are invalid.

    Parameters:
    createcarpool_id: int (required)
    available_seats: int (optional)
    start_location: str (optional)
    end_location: str (optional)
    departure_time: datetime (optional)
    arrival_time: datetime (optional)
    contribution_per_km: float (optional)
    distance_km: float (optional)
    add_note: str (optional)
    allow_luggage: bool (optional)
    gender_preference: str (optional)
    contact_info: str (optional)
    car_model: str (optional)
    car_number: str (optional)
    total_passenger_allowed: int (optional)

    Returns:
    A JSON response with the status, message and data of the updated carpool.
    If the update is successful, it will return a 200 status code with a success message and the updated carpool details.
    If the update fails, it will return a 400 status code with an error message and the error details.
    """
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
        serializer = CreateCarpoolSerializer(carpool)

        return Response({"status":"success", "message":"Carpool updated", "data":{"carpool updated data": serializer.data} }, status=status.HTTP_200_OK)
        
    except CreateCarpool.DoesNotExist:
        return Response({"status":"fail", "message":"Carpool not found"}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
## Delete Carpool
@api_view(['DELETE'])
@permission_classes([IsDriverCustom])
def delete_carpool(request):
    """
    Delete a carpool created by the user.

    This API will delete a carpool created by the user.
    It will only delete the carpool if the user is the creator of the carpool or an admin.
    It will also validate the input fields and return an error if any of the fields are invalid.

    Parameters:
    carpool_id: int (required)

    Returns:
    A JSON response with the status, message and data of the deleted carpool.
    If the delete is successful, it will return a 200 status code with a success message and the deleted carpool details.
    If the delete fails, it will return a 400 status code with an error message and the error details.
    """
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
@permission_classes([IsDriverOrPassengerCustom])
def view_my_carpools(request):
    """
    This API will fetch the details of all the carpools created by the logged-in driver.
    It will return two lists of carpools: one for upcoming carpools and one for past carpools.
    The carpools will be sorted in ascending order of departure time for upcoming carpools and in descending order of departure time for past carpools.
    - Returns a JSON response with the status, message and data of the carpools.
    - If there are no carpools found, it will return a 404 status code with a message "No carpools found".
    """
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
