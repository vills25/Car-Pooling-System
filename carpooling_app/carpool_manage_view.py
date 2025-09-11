from .custom_jwt_auth import IsDriverCustom
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from .models import User, CreateCarpool, Booking
from .serializers import CreateCarpoolSerializer
from .user_authentication import activity

# Create Carpool (driver only)
@api_view(['POST'])
@permission_classes([IsDriverCustom])
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

    # check if carpool creator is Driver.
    if user.role != "driver":
        return Response({"status":"fail","message":"Only drivers can create carpools"}, status=status.HTTP_403_FORBIDDEN)

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

            serializer = CreateCarpoolSerializer(carpool)
            return Response({"status":"success", "message":"Carpool added", "Carpool data": serializer.data}, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({"status":"error","message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    