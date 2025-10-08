from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .user_auth import *
from .carpool_view import *
from .booking_view import *
from .admin_view import *

urlpatterns = [
    #-------- AUTHENTICATION & USER --------#
    path('register/', register_user),
    path('login/', login_user),
    path('logout_user/', logout_user),
    path('profile/my-profile/',view_profile),
    path('profile/user-dashboard/', user_dashboard),
    path('profile/update-profile/', update_profile),
    path('profile/delete-profile/', delete_profile),
    path('profile/forgot-password/', forgot_password),
    path('profile/reset-password/', reset_password),
    path('profile/contact-us/', contact_us),

    #-------- ADMIN --------#
    path('admin/view-users/', admin_view_users),
    path('admin/view-activities/', view_all_activities),
    path('admin/user-action/', admin_active_deactive_user),
    path('admin/carpools/', admin_view_carpools),
    path('admin/carpool-bookings/', admin_view_bookings),
    path('admin/reports/', admin_full_report),
    path('admin/user-dashboard-report/', user_dashboard_report),

    #-------- PUBLIC --------#
    path("carpool/detail/",carpool_detail), 
    path("carpool/search-carpools/",search_carpools),
    path("carpool/sort-carpools/",sort_carpools_by),
    path("carpool/find-nearby-carpools/",find_nearby_carpools),

    #-------- CREATE CARPOOL --------#
    path('carpool/create/', create_carpool),
    path('carpool/update/', update_carpool),
    path('carpool/delete/', delete_carpool),
    path('carpool/my-carpools/', view_my_carpools),
    path('carpool/view-passengers/', view_booked_passenger),
    path('carpool/start-end-rides/', start_end_ride_driver),

    #-------- BOOK CARPOOL --------#
    path("booking/create/",book_carpool),
    path("booking/my-bookings/",my_bookings_info),
    path('booking/update/', update_my_booking),
    path('booking/delete/',cancel_booking),
    path('booking/filter/', filter_bookings),
    path("driver/booking-requests/", driver_view_booking_requests),
    path("driver/booking-action/", driver_approve_reject_booking),
    path('ride_reminder_notifications/',ride_reminder_notifications),
    path('review/', give_review_rating),
    path('driver-info/',view_driver_info),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
