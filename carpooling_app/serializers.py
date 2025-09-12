from .models import *
from rest_framework import serializers

## User serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'username', 'first_name', 'last_name', 'email', 
                  'phone_number', 'profile_pic', 'role', 'is_active', 'address']

## Carpool Serializer
class CreateCarpoolSerializer(serializers.ModelSerializer):
    driver = serializers.CharField(source="carpool_creator_driver.first_name", read_only=True)
    class Meta:
        model = CreateCarpool
        fields = ['createcarpool_id','driver','start_location','end_location','departure_time','arrival_time','available_seats','contribution_per_passenger','add_note','created_at','total_passenger_allowed','contact_info','updated_at','updated_by']

## Book carpool serializer
class BookingSerializer(serializers.ModelSerializer):
    passenger = UserSerializer(source="passenger_name", read_only=True)
    carpool = CreateCarpoolSerializer(source="fkCreateCarpool", read_only=True)
    class Meta:
        model = Booking
        fields = ['booking_id','carpool','passenger','seat_book','contribution_amount','booking_status','booked_by','booked_at','pickup_location','drop_location','updated_at','updated_by']

## Activity Serializer
class ActivitySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = Activity
        fields = ['date_time','user','details']

## Transaction Serializer
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['transaction_id','booking','amount','payment_status','created_at','created_by']