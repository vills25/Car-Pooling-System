from django.contrib import admin
from .models import *

admin.site.site_header = "Carpooling system Admin Corner"
admin.site.site_title = "Carpooling"
admin.site.index_title = "Carpooling Admin" 

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'email', 'role','is_active')
    search_fields = ['username', 'email', 'first_name']

class UserDashboardInfoAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_carpools', 'total_bookings', 'total_earning', 'updated_at')
    search_fields = ['user']

class CreateCarpoolAdmin(admin.ModelAdmin):
    list_display = ('createcarpool_id','carpool_creator_driver','start_location','end_location','departure_time','carpool_ride_status','contribution_per_km','distance_km')
    search_fields = ['carpool_creator_driver','createcarpool_id']

class BookingAdmin(admin.ModelAdmin):
    list_display = ('carpool_driver_name','booking_id','pickup_location','drop_location','passenger_name','booking_status', 'distance_travelled','booked_at','booked_by')
    search_fields = ['carpool_driver_name','passenger_name']

class ActivityAdmin(admin.ModelAdmin):
    list_display = ('date_time','user','details')
    search_fields= ['user']

class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone_number', 'your_message', 'created_at')
    search_fields = ['name', 'email', 'phone_number']

class ReviewRatingAdmin(admin.ModelAdmin):
    list_display = ('review_id', 'review_given_by', 'review_for', 'carpool_driver','booking_person_name', 'rating')
    search_fields = ['review_id', 'review_given_by', 'review_for']

class TokenBlacklistLogoutAdmin(admin.ModelAdmin):
    list_display = ('user','is_expired','expire_datetime','token')

admin.site.register(User, UserAdmin)
admin.site.register(UserDashboardInfo,UserDashboardInfoAdmin)
admin.site.register(CreateCarpool,CreateCarpoolAdmin)
admin.site.register(Booking,BookingAdmin)
admin.site.register(Activity,ActivityAdmin) 
admin.site.register(Contact,ContactAdmin)
admin.site.register(ReviewRating,ReviewRatingAdmin)
admin.site.register(TokenBlacklistLogout,TokenBlacklistLogoutAdmin)