from django.contrib import admin
from .models import *

admin.site.site_header = "Carpooling system Admin Corner"
admin.site.site_title = "Carpooling"
admin.site.index_title = "Carpooling Admin" 

admin.site.register(Person)
admin.site.register(CreateCarpool)
admin.site.register(Booking)
admin.site.register(Activity)
admin.site.register(Transaction)

