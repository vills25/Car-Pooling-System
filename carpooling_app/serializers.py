from rest_framework import serializers
from .models import *

## User serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'username', 'first_name', 'last_name','email', 'phone_number', 'profile_pic','role', 'is_active', 'address', 'gender', 'earning']

## User Detail serializer
class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'first_name']

## User Dashboard Serializer
class UserDashboardInfoSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.first_name", read_only=True)
    class Meta:
        model = UserDashboardInfo
        fields = ['user','total_carpools', 'total_bookings', 'total_earning']

## Carpool Serializer
class CreateCarpoolSerializer(serializers.ModelSerializer):
    driver = serializers.CharField(source="carpool_creator_driver.first_name", read_only=True)
    driver_average_rating = serializers.SerializerMethodField()
    updated_by = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = CreateCarpool
        fields = ['createcarpool_id', 'driver', 'driver_average_rating','carpool_ride_status','start_location', 'end_location','departure_time', 'arrival_time','available_seats', 'total_passenger_allowed','contribution_per_km', 
                  'distance_km','add_note', 'allow_luggage','gender_preference','contact_info','car_model', 'car_number', 'is_ev_vehicle','created_at','updated_at', 'updated_by']

    def get_driver_average_rating(self, obj):
        from django.db.models import Avg
        avg = ReviewRating.objects.filter(review_for=obj.carpool_creator_driver).aggregate(Avg("rating"))["rating__avg"] or 0
        return round(float(avg), 2)

## Carpool Detail Serializer
class CarpoolDetailSerializer(serializers.ModelSerializer):
    carpool_driver_name = serializers.SerializerMethodField()
    updated_by = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = CreateCarpool
        fields = ['createcarpool_id', 'carpool_driver_name','carpool_ride_status','start_location', 'end_location','departure_time', 'arrival_time','available_seats', 'total_passenger_allowed',
                  'contribution_per_km', 'distance_km','add_note', 'contact_info', 'allow_luggage','car_model', 'car_number','is_ev_vehicle','updated_by']

    def get_carpool_driver_name(self, obj):
        return obj.carpool_creator_driver.first_name if obj.carpool_creator_driver else None

## Booking Serializers
class BookingSerializer(serializers.ModelSerializer):
    passenger = UserSerializer(source="passenger_name", read_only=True)
    carpool = CreateCarpoolSerializer(source="carpool_driver_name", read_only=True)
    booked_by = serializers.CharField(source="booked_by.first_name", read_only=True)
    updated_by = serializers.CharField(source='updated_by.username', read_only=True)
    class Meta:
        model = Booking
        fields = ['booking_id', 'carpool', 'passenger','seat_book', 'distance_travelled','contribution_amount', 'payment_mode','booking_status', 'ride_status','booked_by',
                   'booked_at','pickup_location', 'drop_location', 'contact_info','updated_at', 'updated_by']

## Booking Detail Serializer
class BookingDetailSerializer(serializers.ModelSerializer):
    passenger_name = serializers.SerializerMethodField()
    carpool_detail = CarpoolDetailSerializer(source="carpool_driver_name", read_only=True)
    updated_by = serializers.CharField(source='updated_by.username', read_only=True)
    booked_by = serializers.CharField(source="booked_by.first_name", read_only=True)
    class Meta:
        model = Booking
        fields = ['booking_id', 'passenger_name', 'seat_book', 'distance_travelled', 'contribution_amount', 'payment_mode', 'booking_status', 'ride_status', 'booked_by', 'booked_at',
            'pickup_location', 'drop_location', 'contact_info','updated_at', 'updated_by','carpool_detail']

    def get_passenger_name(self, obj):
        return obj.passenger_name.first_name if obj.passenger_name else None

## Activity Serializer
class ActivitySerializer(serializers.ModelSerializer):
    # user = UserSerializer(read_only=True)
    class Meta:
        model = Activity
        fields = ['date_time', 'details']

## Contact / Visitor Enquiry Serializer
class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['contact_id', 'name', 'email', 'phone_number','your_message', 'created_at', "updated_at", "updated_by"]

## Review Rating Serializer
class ReviewRatingSerializer(serializers.ModelSerializer):
    review_given_by_name = serializers.CharField(source="review_given_by.username", read_only=True)
    review_given_to_name = serializers.CharField(source="review_for.username", read_only=True)
    carpool_id = serializers.IntegerField(source="carpool.createcarpool_id", read_only=True)
    booking_id = serializers.IntegerField(source="booking.booking_id", read_only=True)
    # updated_by = serializers.CharField(source='updated_by.username', read_only=True)
    class Meta:
        model = ReviewRating
        fields = ["review_id", "review_given_by_name", "review_given_to_name","carpool_id","booking_id", "rating", "comment"]
