from datetime import timedelta
from .user_auth import activity
from .utils import *
from .models import CreateCarpool
from .serializers import CreateCarpoolSerializer
from .custom_jwt_auth import IsAdminOrDriverCustom, IsAuthenticatedCustom, IsDriverCustom, IsDriverOrPassengerCustom
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
    Smart search with location name + coordinates support.
    """
    start = request.data.get("start_location", "").strip()
    end = request.data.get("end_location", "").strip()
    date = request.data.get("date")
    start_latitude = request.data.get("start_latitude")
    start_longitude = request.data.get("start_longitude")
    end_latitude = request.data.get("end_latitude")
    end_longitude = request.data.get("end_longitude")

    try:
        # Base query: upcoming rides with available seats
        qs = CreateCarpool.objects.filter(available_seats__gt=0, departure_time__gte=timezone.now())

        # Date filter (optional)
        if date:
            qs = qs.filter(departure_time__icontains=date)

        final_results = []

        # Get user's start/end coordinates either from request OR geocoding
        if start_latitude and start_longitude:
            user_start_lat, user_start_lon = float(start_latitude), float(start_longitude)
        else:
            user_start_lat, user_start_lon = get_lat_lng_cached(start) if start else (None, None)

        if end_latitude and end_longitude:
            user_end_lat, user_end_lon = float(end_latitude), float(end_longitude)
        else:
            user_end_lat, user_end_lon = get_lat_lng_cached(end) if end else (None, None)

        print(">>>> User start coordinates:", user_start_lat, user_start_lon)
        print(">>>> User end coordinates:", user_end_lat, user_end_lon)

        # Iterate over base query
        for carpool in qs:
            # Calculate distance if not set
            if not carpool.distance_km or float(carpool.distance_km) == 0:
                carpool.distance_km = auto_calculate_distance(
                    carpool.start_location,
                    carpool.end_location,
                    start_lat=carpool.latitude_start,
                    start_lon=carpool.longitude_start,
                    end_lat=carpool.latitude_end,
                    end_lon=carpool.longitude_end
                )
                carpool.save(update_fields=['distance_km'])

            print(">>>> Carpool start coordinates:", carpool.latitude_start, carpool.longitude_start)
            print(">>>> Carpool end coordinates:", carpool.latitude_end, carpool.longitude_end)

            # Start location match (name OR coordinate)
            start_match = matches_location(start,carpool.start_location,user_start_lat,user_start_lon,carpool.latitude_start,carpool.longitude_start)

            # End location match (name OR coordinate)
            end_match = matches_route( end,carpool,user_end_lat,user_end_lon)

            print(">>>> Start match:", start_match)
            print(">>>> End match:", end_match)

            if start_match and end_match:
                final_results.append(carpool)

        if not final_results:
            return Response({"status": "fail", "message": "No carpools found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreateCarpoolSerializer(final_results, many=True)
        formatted_data = km_inr_format(serializer.data)
        return Response({"status": "success","message": "Carpools fetched","data": {"Carpools": formatted_data}}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## sort carpools by date, location, available seats, departure time, arrivval time, luggage.
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
    currunt_time = timezone.now()
    try:

        queryset = CreateCarpool.objects.filter(available_seats__gt = 0,departure_time__gte = currunt_time).order_by('-departure_time')

        start_location = request.data.get('start_location')
        end_location = request.data.get('end_location')
        date = request.data.get('date')
        available_seats = request.data.get('available_seats')
        gender_preference = request.data.get('gender_preference')
        luggage = request.data.get("luggage_allowed")
        prefer_ev_vehicle = request.data.get("prefer_ev_vehicle")
        
        if start_location:
            queryset = queryset.filter(start_location__icontains = start_location)

        if end_location:
            queryset = queryset.filter(end_location__icontains = end_location)

        if date:
            queryset = queryset.filter(departure_time__icontains = date)

        if luggage is not None:
            luggage_bool = str(luggage).lower() == "true"
            queryset = queryset.filter(allow_luggage = luggage_bool)  

        if gender_preference:
            queryset = queryset.filter(gender_preference__iexact = gender_preference)

        if prefer_ev_vehicle is not None:
            prefer_ev_vehicle = str(prefer_ev_vehicle).lower() == "true"
            queryset = queryset.filter(is_ev_vehicle = prefer_ev_vehicle)

        if available_seats:
            try:
                seats = int(available_seats)
                queryset = queryset.filter(available_seats__gte = seats) # equal or greter then entered seats
            except:
                return Response({"status": "fail", "message": "available_seats must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        if not queryset.exists():
            return Response({"status": "fail", "message": "No matching Carpools found"}, status=status.HTTP_404_NOT_FOUND)

        activity(user, f"{request.user.first_name} sorted Carpools")
        serializer = CreateCarpoolSerializer(queryset, many=True)

        return Response({"status": "success", "message": "Carpools fetched", "data":{"Carpools": km_inr_format(serializer.data)}}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## find nearby carpools - show only upcoming rides with seats more than 0 , expired time ride hidden, enter location and find all carpool around 20km
@api_view(["POST"])
@permission_classes([AllowAny])
def find_nearby_carpools(request):
    """
    Find nearby carpools within a 20 KM radius.
    Input:
        - location (string) OR latitude & longitude
    Output:
        - List of nearby carpools sorted by distance (only upcoming & with available seats)
    """
    location_name = request.data.get("location")
    location_latitude = request.data.get("location_latitude")
    location_longitude = request.data.get("location_longitude")

    if not location_name and (location_latitude is None or location_longitude is None):
        return Response({"status": "fail","message": "Location name OR latitude & longitude required"}, status=status.HTTP_400_BAD_REQUEST)

    if location_latitude is not None and location_longitude is not None:
        try:
            user_lat, user_lon = float(location_latitude), float(location_longitude)
        except ValueError:
            return Response({"status": "fail","message": "Invalid latitude/longitude format" }, status=status.HTTP_400_BAD_REQUEST)
    else:
        user_lat, user_lon = get_lat_lng_cached(location_name)
        if user_lat is None or user_lon is None:
            return Response({"status": "fail", "message": "Invalid location or coordinates not found"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        upcoming_carpools = CreateCarpool.objects.filter( departure_time__gte=timezone.now(), available_seats__gt=0 )

        nearby_carpools = []

        for carpool in upcoming_carpools:
            # Use DB coordinates if available, else geocode
            start_lat = carpool.latitude_start
            start_lon = carpool.longitude_start

            if start_lat is None or start_lon is None:
                start_lat, start_lon = get_lat_lng_cached(carpool.start_location)
            
            # Skip if coordinates are missing
            if start_lat is None or start_lon is None:
                continue

            distance_km = geodesic((user_lat, user_lon), (start_lat, start_lon)).km

            # Filter within 10 KM radius
            if distance_km <= 10:
                carpool_data = CreateCarpoolSerializer(carpool).data
                carpool_data["distance_from_you"] = f"{distance_km:.2f} KM"
                carpool_data["distance_value"] = distance_km
                nearby_carpools.append(carpool_data)

        # Sort by distance
        for i in range(len(nearby_carpools)):
            for j in range(i + 1, len(nearby_carpools)):
                if nearby_carpools[i]["distance_value"] > nearby_carpools[j]["distance_value"]:
                    temp = nearby_carpools[i]
                    nearby_carpools[i] = nearby_carpools[j]
                    nearby_carpools[j] = temp

        for carpool in nearby_carpools:
            del carpool["distance_value"]

        return Response({"status": "success","total_results": len(nearby_carpools), "data": nearby_carpools}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({ "status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#-------- CARPOOL CRUD --------#

## Create Carpool (Anyone authenticated user can book carpool)
@api_view(['POST'])
@permission_classes([IsAuthenticatedCustom])
def create_carpool(request):
    """
    Create a new carpool by driver.

    Parameters:
    start_location (str): required
    end_location (str): required
    departure_time (datetime): required
    arrival_time (datetime): required
    available_seats (int): required
    total_passenger_allowed (int): required
    contribution_per_km (float): required
    distance_km (float): optional (auto-calculated if not provided)
    latitude_start, longitude_start, latitude_end, longitude_end: optional (for precise calculation)
    """

    user = request.user
    current_time = timezone.now()
    two_hours_ahead = current_time + timedelta(hours=1)

    # check if user already has an active or upcoming journey
    if CreateCarpool.objects.filter(carpool_creator_driver=user,departure_time__lte=two_hours_ahead,arrival_time__gte=current_time).exists():
        return Response({"status": "fail", "message": "You already have an active or upcoming journey within 1 hour."},status=status.HTTP_400_BAD_REQUEST)

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
    get_is_ev_vehicle = request.data.get('is_ev_vehicle')
    # Optional cordinates fields
    get_latitude_start = request.data.get("latitude_start")
    get_longitude_start = request.data.get("longitude_start")
    get_latitude_end = request.data.get("latitude_end")
    get_longitude_end = request.data.get("longitude_end")

    # Required fields validation
    for field in ["start_location", "end_location", "departure_time", "available_seats", "total_passenger_allowed"]:
        if not request.data.get(field):
            return Response({"status": "fail", "message": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        available_seats = int(get_available_seats)
        total_allowed = int(get_total_passenger_allowed)

        if available_seats < 0 or total_allowed <= 0:
            return Response({"status": "fail", "message": "available_seats must be >=0 and total_passenger_allowed >0"}, status=status.HTTP_400_BAD_REQUEST)
        
        if available_seats > total_allowed:
            return Response({"status": "fail", "message": "available_seats cannot be greater than total_passenger_allowed"}, status=status.HTTP_400_BAD_REQUEST)
        
    except ValueError:
        return Response({"status": "fail", "message": "available_seats and total_passenger_allowed must be integers"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        distance_val = float(get_distance_km) if get_distance_km else 0.0
    except:
        distance_val = 0.0

    try:
        if distance_val <= 0:
            # Use given coordinates if available
            if get_latitude_start and get_longitude_start and get_latitude_end and get_longitude_end:
                try:
                    distance_val = get_road_distance_osrm(
                        float(get_latitude_start), float(get_longitude_start),
                        float(get_latitude_end), float(get_longitude_end)
                    )
                    if distance_val is None:
                        distance_val = auto_calculate_distance(
                            get_start_location, get_end_location,
                            start_lat=float(get_latitude_start), start_lon=float(get_longitude_start),
                            end_lat=float(get_latitude_end), end_lon=float(get_longitude_end)
                        )
                except Exception:
                    distance_val = 0.0

            #If no coordinates, use geocoding
            else:
                start_lat, start_lon = get_lat_lng_cached(get_start_location)
                end_lat, end_lon = get_lat_lng_cached(get_end_location)
                distance_val = get_road_distance_osrm(start_lat, start_lon, end_lat, end_lon)

                if distance_val is None:
                    distance_val = auto_calculate_distance(
                        get_start_location, get_end_location,
                        start_lat=start_lat, start_lon=start_lon,
                        end_lat=end_lat, end_lon=end_lon
                    )

    except Exception:
        distance_val = 0.0

    # If still no distance found
    if distance_val <= 0:
        distance_val = 0.0

    try:
        with transaction.atomic():
            carpool = CreateCarpool.objects.create(
                carpool_creator_driver = user,
                start_location = get_start_location,
                end_location = get_end_location,
                latitude_start = float(get_latitude_start) if get_latitude_start else start_lat,
                longitude_start = float(get_longitude_start) if get_longitude_start else start_lon,
                latitude_end = float(get_latitude_end) if get_latitude_end else end_lat,
                longitude_end = float(get_longitude_end) if get_longitude_end else end_lon,
                departure_time = get_departure_time,
                arrival_time = get_arrival_time,
                available_seats = available_seats,
                total_passenger_allowed = total_allowed,
                contribution_per_km = get_contribution_per_km,
                distance_km = distance_val,
                add_note = get_add_note,
                allow_luggage = get_allow_luggage,
                gender_preference = get_gender_preference,
                contact_info = get_contact_info,
                car_model = get_car_model,
                car_number = get_car_number,
                is_ev_vehicle = get_is_ev_vehicle
            )

            # Auto-assign driver role if not already
            if user.role != "driver":
                user.role = "driver"
                user.save()

            activity(user, f"{user.username} created a new carpool {carpool.createcarpool_id} and became driver")

            serializer = CreateCarpoolSerializer(carpool)
            return Response({"status": "success", "message": "Carpool created successfully", "data": {"Carpool data": km_inr_format(serializer.data)}},status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## user who created carpool will assigned driver role and only he can with driver role UPDATE/DELETE/VIEW his carpool details.
## Edit Carpool details 
@api_view(['PUT'])
@permission_classes([IsAdminOrDriverCustom])
def update_carpool(request):
    """
    This API will update the details of a carpool created by the user.
    It will only update the details of the carpool if the user is the creator of the carpool.

    Parameters:
    createcarpool_id: int (required)

    Returns:
    A JSON response with the status, message and data of the updated carpool.
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
    get_is_ev_vehicle = request.data.get("is_ev_vehicle")
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
        if get_is_ev_vehicle is not None:
            carpool.is_ev_vehicle = bool(get_is_ev_vehicle)
            
        # Handle total passengers with validation
        if get_total_passenger_allowed is not None:
            try:
                carpool.total_passenger_allowed = int(get_total_passenger_allowed)
            except ValueError:
                return Response({"status":"fail", "message":"total_passenger_allowed must be integer"}, status=status.HTTP_400_BAD_REQUEST)

        carpool.updated_by = user
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
@permission_classes([IsAdminOrDriverCustom])
def delete_carpool(request):
    """
    Delete a carpool created by the user.
    It will only delete the carpool if the user is the creator of the carpool or an admin.

    Parameters:
    carpool_id: int (required)

    Returns:
    A JSON response with the status, message and data of the deleted carpool.
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
    """
    user = request.user

    try:
        currunt_time = timezone.now()
        upcoming_carpool = CreateCarpool.objects.filter(carpool_creator_driver=user, departure_time__gte=currunt_time).order_by("departure_time")
        past_carpool = CreateCarpool.objects.filter(carpool_creator_driver=user, departure_time__lt=currunt_time).order_by("-departure_time")
        data = {
            "upcoming_carpool": CreateCarpoolSerializer(upcoming_carpool, many=True).data,
            "past_carpool": CreateCarpoolSerializer(past_carpool, many=True).data
        }
        
        return Response({"status":"success","message":"Carpools data fetched", "Data":{"Carpools": km_inr_format(data)}}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## start or end a ride
@api_view(["POST"])
@permission_classes([IsAdminOrDriverCustom])
def start_end_ride_driver(request):
    """
    This API is used to start or end a ride as a driver.

    Parameters:
    carpool_id (int): required
    start_ride (bool): optional
    end_ride (bool): optional

    Returns:
    A JSON response with the status, message, and ride status of the carpool.

    If the ride has already been started or completed, it will return a 400 status code with a message "Ride already active or completed."

    If the ride is cancelled due to arrival time being passed, it will return a 400 status code with a message "Cannot start ride, arrival time passed. Ride cancelled."

    If the ride is completed successfully, it will return a 200 status code with a message "Ride completed successfully."

    If the request is invalid, it will return a 400 status code with a message "Please pass 'start_ride' or 'end_ride' as True."

    If an unexpected error occurs, it will return a 500 status code with a message describing the error.
    """
    try:
        carpool_id = request.data.get("carpool_id")
        if not carpool_id:
            return Response({"status": "fail", "message": "carpool_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            carpool = CreateCarpool.objects.get(createcarpool_id=carpool_id)
        except CreateCarpool.DoesNotExist:
            return Response({"status": "fail", "message": "Carpool not found."}, status=status.HTTP_404_NOT_FOUND)

        if carpool.carpool_creator_driver != request.user:
            return Response({"status": "fail", "message": "You are not the driver of this carpool."}, status=status.HTTP_403_FORBIDDEN)

        start_ride = request.data.get("start_ride", False)
        end_ride = request.data.get("end_ride", False)
        current_time = timezone.now()

        # ---------- START RIDE ----------
        if start_ride:
            if carpool.carpool_ride_status in ["active", "completed"]:
                return Response({"status": "fail", "message": "Ride already active or completed."}, status=status.HTTP_400_BAD_REQUEST)

            if current_time > carpool.arrival_time:
                carpool.carpool_ride_status = "cancelled"
                carpool.save()
                Booking.objects.filter(carpool_driver_name=carpool).update(ride_status="cancelled", booking_status="cancelled")
                return Response({"status": "fail", "message": "Cannot start ride, arrival time passed. Ride cancelled."}, status=status.HTTP_400_BAD_REQUEST)

            carpool.carpool_ride_status = "active"
            carpool.save()
            Booking.objects.filter(carpool_driver_name=carpool).update(ride_status="active")

            activity(request.user, f"Started ride for Carpool ID: {carpool_id}")
            return Response({"status": "success", "message": "Ride started successfully.", "ride_status": carpool.carpool_ride_status}, status=status.HTTP_200_OK)

        # ---------- END RIDE ----------
        elif end_ride:
            if carpool.carpool_ride_status != "active":
                return Response({"status": "fail", "message": "Cannot end ride. Ride is not active."}, status=status.HTTP_400_BAD_REQUEST)

            carpool.carpool_ride_status = "completed"
            carpool.save()
            Booking.objects.filter(carpool_driver_name=carpool).update(ride_status="completed", booking_status="confirmed")

            activity(request.user, f"Completed ride for Carpool ID: {carpool_id}")
            return Response({"status": "success", "message": "Ride completed successfully.", "ride_status": carpool.carpool_ride_status}, status=status.HTTP_200_OK)

        else:
            return Response({"status": "fail", "message": "Please pass 'start_ride' or 'end_ride' as True."}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

