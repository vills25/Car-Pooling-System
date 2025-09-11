from django.contrib import admin
from .models import *

admin.site.site_header = "Carpooling system Admin Corner"
admin.site.site_title = "Carpooling"
admin.site.index_title = "Carpooling Admin" 

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'email', 'role','is_active')
    search_fields = ['username', 'email', 'first_name']

class CreateCarpoolAdmin(admin.ModelAdmin):
    list_display = ('carpool_creator_driver','start_location','end_location','contribution_per_passenger','total_passenger_allowed')
    search_fields = ['carpool_creator_driver','createcarpool_id']

class BookingAdmin(admin.ModelAdmin):
    list_display = ('fkCreateCarpool','passenger_name','booking_status')
    search_fields = ['fkCreateCarpool','passenger_name']

class ActivityAdmin(admin.ModelAdmin):
    list_display = ('date_time','user','details')
    search_fields= ['user']

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('booking','created_by','amount','payment_status')
    search_fields = ['booking']

admin.site.register(User, UserAdmin)
admin.site.register(CreateCarpool,CreateCarpoolAdmin)
admin.site.register(Booking,BookingAdmin)
admin.site.register(Activity,ActivityAdmin)
admin.site.register(Transaction,TransactionAdmin)

