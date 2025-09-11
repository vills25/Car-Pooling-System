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


    #-------- FIND & BOOK CARPOOL --------#

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
