from django.urls import path
from .user_authentication import *
from .carpool_manage_view import *
from .booking_passanger_view import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    #-------- AUTHENTICATION & USER --------#
    path('register_user/', register_user),
    path('login_user/', login_user),
    path('view_profile/',view_profile),
    path('update_profile/', update_profile),
    path('delete_profile/', delete_profile),
    path('forgot_password/', forgot_password),
    path('reset_password/', reset_password),

    #-------- CREATE CARPOOL --------#
    path('create_carpool/', create_carpool),
    path('update_carpool/', update_carpool),
    path('delete_carpool/', delete_carpool),
    path('view_my_carpools/', view_my_carpools),
    path("carpool_detail/",carpool_detail),
    path("search_carpools/",search_carpools),
    path("sort_carpools_by/",sort_carpools_by),

    #-------- FIND & BOOK CARPOOL --------#
    path("book_carpool/",book_carpool),
    path("my_bookings_info/",my_bookings_info),
    path('update_my_booking/', update_my_booking),
    path('cancel_booking/',cancel_booking),
    path('filter_bookings/', filter_bookings),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
