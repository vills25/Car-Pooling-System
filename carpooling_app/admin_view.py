from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .user_auth import activity
from .custom_jwt_auth import IsAdminCustom
from .models import Activity, User, CreateCarpool, Booking
from .serializers import ActivitySerializer,UserSerializer, CreateCarpoolSerializer, BookingSerializer

def is_admin(user):
    return user.role == "admin" or getattr(user, "is_superuser", False)

## View all User for admin view
@api_view(['GET'])
@permission_classes([IsAdminCustom])
def admin_view_users(request):
    try:
        if not is_admin(request.user):
            return Response({"status": "fail", "message": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        users = User.objects.all().order_by("user_id")
        serializer = UserSerializer(users, many=True)
        return Response({"status": "success", "Users": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

## View all Activity of all user's by Admin
@api_view(["GET"])
@permission_classes([IsAdminCustom]) 
def view_all_activities(request):
    logs = Activity.objects.all().order_by("-date_time")[:200]  # last 200 logs
    serializer = ActivitySerializer(logs, many=True)
    return Response({"status": "success", "message": "Activity logs fetched", "logs data": serializer.data},status=status.HTTP_200_OK)

## Activate/Deactivate user
@api_view(['PUT'])
@permission_classes([IsAdminCustom])
def admin_active_deactive_user(request):
    if not is_admin(request.user):
        return Response({"status": "fail", "message": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    user_id = request.data.get("user_id")
    try:
        enter_user = User.objects.get(user_id=user_id)
        enter_user.is_active = not enter_user.is_active
        enter_user.save()
        activity(request.user, f"Admin toggled user {enter_user.username} active={enter_user.is_active}")
        return Response({"status": "success", "message": f"User {enter_user.username} active={enter_user.is_active}"}, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({"status": "fail", "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAdminCustom])
def admin_view_carpools(request):
    try:
        if not is_admin(request.user):
            return Response({"status": "fail", "message": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        carpools = CreateCarpool.objects.all().order_by("-created_at")
        serializer = CreateCarpoolSerializer(carpools, many=True)
        return Response({"status": "success", "Carpools": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAdminCustom])
def admin_view_bookings(request):
    try:
        if not is_admin(request.user):
            return Response({"status": "fail", "message": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        bookings = Booking.objects.all().order_by("-booked_at")
        serializer = BookingSerializer(bookings, many=True)
        return Response({"status": "success", "Bookings": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)