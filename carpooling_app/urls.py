from django.urls import path
from .user_authentication import *
from .carpool_manage_view import *
from .booking_passanger_view import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    #-------- AUTHENTICATION & USER --------#
    path('register/', register_user),
    path('login/', login_user),
    path('profile/my-profile/',view_profile),
    path('profile/update-profile/', update_profile),
    path('profile/delete-profile/', delete_profile),
    path('profile/forgot-password/', forgot_password),
    path('profile/reset-password/', reset_password),

    #-------- PUBLIC --------#
    path("carpool/detail/",carpool_detail), 
    path("carpool/search-carpools/",search_carpools),
    path("carpool/sort-carpools/",sort_carpools_by),

    #-------- CREATE CARPOOL --------#
    path('carpool/create/', create_carpool),
    path('carpool/update/', update_carpool),
    path('carpool/delete/', delete_carpool),
    path('carpool/my-carpools/', view_my_carpools),
    path('carpool/view-passengers/', view_booked_passenger),

    #-------- BOOK CARPOOL --------#
    path("booking/create/",book_carpool),
    path("booking/my-bookings/",my_bookings_info),
    path('booking/update/', update_my_booking),
    path('booking/delete/',cancel_booking),
    path('booking/filter/', filter_bookings),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
