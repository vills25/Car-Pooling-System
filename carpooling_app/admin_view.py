from django.db.models import Sum
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .user_auth import activity
from .custom_jwt_auth import IsAdminCustom
from .models import Activity, User, CreateCarpool, Booking
from .serializers import ActivitySerializer, BookingDetailSerializer,UserSerializer, CreateCarpoolSerializer


## View all User for admin view
@api_view(['GET'])
@permission_classes([IsAdminCustom])
def admin_view_users(request):
    """
    Returns a list of all users in the system.
    Only accessible to admin users.
    """
    try:
        users = User.objects.all().order_by("user_id")
        serializer = UserSerializer(users, many=True, context={'request': request})
        return Response({"status": "success", "Users": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## View all Activity of all user's by Admin
@api_view(["GET"])
@permission_classes([IsAdminCustom]) 
def view_all_activities(request):
    """
    This API will fetch all activity logs of all users in the system.
    Only accessible to admin users.
    Returns a JSON response with the status, message and data of the activity logs.
    If there are no activity logs found, it will return a 404 status code with a message "No activity logs found".
    """
    logs = Activity.objects.all().order_by("-date_time")
    serializer = ActivitySerializer(logs, many=True)
    return Response({"status": "success", "message": "Activity logs fetched", "logs data": serializer.data},status=status.HTTP_200_OK)

## Activate/Deactivate user
@api_view(['PUT'])
@permission_classes([IsAdminCustom])
def admin_active_deactive_user(request):
    """
    Toggle the active status of a user.
    Only accessible to admin users.
    Parameters:
    user_id (int): The id of the user to toggle.
    Returns:
    Response: A JSON response with the status, message and data of the user.
    If the toggle is successful, it will return a 200 status code with a success message and the updated user data.
    If the toggle fails, it will return a 404 status code with an error message if the user is not found.
    """
    user_id = request.data.get("user_id")
    try:
        enter_user = User.objects.get(user_id=user_id)
        enter_user.is_active = not enter_user.is_active
        enter_user.save()
        activity(request.user, f"Admin toggled user {enter_user.username} active={enter_user.is_active}")
        return Response({"status": "success", "message": f"User {enter_user.username} active={enter_user.is_active}"}, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({"status": "fail", "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

## View all Carpool
@api_view(['GET'])
@permission_classes([IsAdminCustom])
def admin_view_carpools(request):
    """
    This API will fetch all the carpools created by all users in the system.
    It will return a list of all carpools sorted in descending order of creation time.
    Only accessible to admin users.
    Returns a JSON response with the status, message and data of the carpools.
    If there are no carpools found, it will return a 404 status code with a message "No carpools found".
    """
    try:
        carpools = CreateCarpool.objects.all().order_by("-created_at")
        serializer = CreateCarpoolSerializer(carpools, many=True)
        return Response({"status": "success", "Carpools": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## View all Bookings
@api_view(['GET'])
@permission_classes([IsAdminCustom])
def admin_view_bookings(request):
    """
    Returns a list of all bookings made by passengers.
    The list is sorted in descending order of booking time.
    Only accessible to admin users.
    """
    try:
        bookings = Booking.objects.all().order_by("-booked_at")
        serializer = BookingDetailSerializer(bookings, many=True)
        return Response({"status": "success", "Bookings": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## Admin dashboard
@api_view(['GET'])
@permission_classes([IsAdminCustom])
def admin_full_report(request):
    """
        This API endpoint returns a report which includes 
            - Top drivers (totalrides count)
            - Busiest routes
            - Highest earner driver
            - Dashboard stats (total revenue, active drivers, weekly bookings, cancellation rate)
            - Reports section (total users, total carpools, total bookings, top drivers, busiest routes)
        Requires admin access.
        """ 
    try:
        # Top drivers (totalrides count)
        top_drivers = User.objects.filter(role="driver").annotate(total_rides=Count("journeys")).order_by("-total_rides")[:5].values_list("username", "total_rides")

        # Busiest routes
        busiest_routes = CreateCarpool.objects.values("start_location", "end_location").annotate(count=Count("createcarpool_id")).order_by("-count")[:5]

        # Highest earner driver
        highest_earner = Booking.objects.filter(booking_status="confirmed").values("carpool_driver_name__carpool_creator_driver__username").annotate(total_earnings=Sum("contribution_amount")).order_by("-total_earnings").first()

        if highest_earner:
            highest_earner_data = {"username": highest_earner["carpool_driver_name__carpool_creator_driver__username"], "amount": highest_earner["total_earnings"],}
        else:
            highest_earner_data = {"username": None, "amount": 0}

        # Dashboard Stats
        total_revenue = Booking.objects.filter(booking_status="confirmed").aggregate(total=Sum("contribution_amount"))["total"] or 0
        active_drivers = User.objects.filter(role="driver", is_active=True).count()
        weekly_bookings = Booking.objects.filter(booked_at__gte=timezone.now() - timedelta(days=7)).count()
        total_bookings = Booking.objects.count()
        total_cancelled = Booking.objects.filter(booking_status="cancelled").count()
        cancellation_rate = round(total_cancelled / total_bookings * 100, 2) if total_bookings else 0

        dashboard_stats = {
            "total_revenue": total_revenue,
            "active_drivers": active_drivers,
            "weekly_bookings": weekly_bookings,
            "cancellation_rate": cancellation_rate,
            "highest_earner": highest_earner_data,
        }

        # Reports Section
        reports = {
            "total_users": User.objects.count(),
            "total_carpools": CreateCarpool.objects.count(),
            "total_bookings": total_bookings,
            "top_drivers": top_drivers,
            "busiest_routes": busiest_routes,
        }

        return Response({"status": "success", "message": "Admin full report", "data": {"reports": reports, "dashboard_stats": dashboard_stats}}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"status": "error", "message": str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
