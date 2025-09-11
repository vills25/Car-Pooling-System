from .models import *
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'username', 'first_name', 'last_name', 'email', 
                  'phone_number', 'profile_pic', 'role', 'is_active', 'address']


class CreateCarpoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreateCarpool
        fields = ['createcarpool_id','carpool_creator_driver','start_location','end_location','departure_time','arrival_time','available_seats','contribution_per_passenger','add_note','created_at','total_passenger_allowed','contact_info']

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['booking_id','fkCreateCarpool','passenger_name','seat_book','contribution_amount','booking_status','booked_by','booked_at','pickup_location','drop_location']

class Activity(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['date_time','user','details']

class Transaction(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['transaction_id','booking','amount','payment_status','created_at','created_by']