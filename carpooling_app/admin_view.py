import os
from django.db.models import Sum
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
from carpooling_app.utils import ride_status_function
from .user_auth import activity
from .custom_jwt_auth import *
from .models import *
from .serializers import *
import io, json
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle


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
        ride_status_function(request)
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
        ride_status_function(request)
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
        highest_earner = Booking.objects.filter(ride_status="completed").values("carpool_driver_name__carpool_creator_driver__username").annotate(total_earnings=Sum("contribution_amount")).order_by("-total_earnings").first()

        if highest_earner:
            highest_earner_data = {"username": highest_earner["carpool_driver_name__carpool_creator_driver__username"], "amount": highest_earner["total_earnings"]}
        else:
            highest_earner_data = {"username": None, "amount": 0}

        # Dashboard Stats
        total_revenue = Booking.objects.filter(ride_status="completed").aggregate(total=Sum("contribution_amount")).get("total", 0)

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


EXPORT_DIR = r"C:\Users\ASUS\OneDrive\Desktop 1\Car-Pooling-System\export"
os.makedirs(EXPORT_DIR, exist_ok=True)

## User data Export
@api_view(["POST"])
@permission_classes([IsAdminCustom])
def user_dashboard_report_export(request):
    get_user_id = request.data.get("user_id")
    if not get_user_id:
        return Response({"status": "error", "message": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(user_id=get_user_id)

        start_date = request.data.get("start_date")  # 2025-10-01
        end_date = request.data.get("end_date")      # 2025-10-10
        carpool_status = request.data.get("carpool_status")  # completed, upcoming, etc.
        booking_status = request.data.get("booking_status")  # confirmed, cancelled, etc.

        carpools = CreateCarpool.objects.filter(carpool_creator_driver=user)
        bookings = Booking.objects.filter(passenger_name=user)

        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                carpools = carpools.filter(departure_time__date__gte=start_date_obj)
                bookings = bookings.filter(booked_at__date__gte=start_date_obj)
            except ValueError:
                return Response({"status": "error", "message": "Invalid start_date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                end_date_obj += timedelta(days=1)
                carpools = carpools.filter(departure_time__lt=end_date_obj)
                bookings = bookings.filter(booked_at__lt=end_date_obj)
            except ValueError:
                return Response({"status": "error", "message": "Invalid end_date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        #STATUS FILTERS
        if carpool_status:
            carpools = carpools.filter(carpool_ride_status__iexact=carpool_status)

        if booking_status:
            bookings = bookings.filter(booking_status__iexact=booking_status)

        # DASHBOARD
        try:
            dashboard = UserDashboardInfo.objects.get(user=user)
        except UserDashboardInfo.DoesNotExist:
            total_carpools = carpools.count()
            total_bookings = bookings.count()
            total_earning = 0
            if user.role == "driver":
                total_earning = carpools.aggregate(total=Sum("contribution_per_km"))["total"] or 0

            dashboard = UserDashboardInfo(
                user=user,
                total_carpools=total_carpools,
                total_bookings=total_bookings,
                total_earning=total_earning,
            )

        # JSON Response Data
        data = {
            "status": "success",
            "message": "User dashboard data fetched successfully.",
            "filters_applied": {
                "start_date": start_date,
                "end_date": end_date,
                "carpool_status": carpool_status,
                "booking_status": booking_status,
            },
            "data": {
                "Dashboard": {
                    "Overview": {
                        "user": user.first_name,
                        "total_carpools": dashboard.total_carpools,
                        "total_bookings": dashboard.total_bookings,
                        "total_earning": str(dashboard.total_earning),
                    },
                    "User": {
                        "user_id": user.user_id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "profile_pic": user.profile_pic.url if user.profile_pic else None,
                        "role": user.role,
                        "is_active": user.is_active,
                        "address": user.address,
                        "gender": user.gender,
                        "earning": str(user.earning),
                    },
                    "carpools": [
                        {
                            "createcarpool_id": c.createcarpool_id,
                            "start_location": c.start_location,
                            "end_location": c.end_location,
                            "departure_time": c.departure_time.strftime("%Y-%m-%d %H:%M:%S") if c.departure_time else None,
                            "arrival_time": c.arrival_time.strftime("%Y-%m-%d %H:%M:%S") if c.arrival_time else None,
                            "available_seats": c.available_seats,
                            "carpool_ride_status": c.carpool_ride_status,
                            "bookings_count": c.bookings.count(),
                        } for c in carpools
                    ],
                    "bookings": [
                        {
                            "booking_id": b.booking_id,
                            "role": "passenger",
                            "carpool_id": b.carpool_driver_name.createcarpool_id if b.carpool_driver_name else None,
                            "start_location": b.pickup_location,
                            "end_location": b.drop_location,
                            "booking_status": b.booking_status,
                            "created_at": b.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(b, 'created_at') else None,
                        } for b in bookings
                    ],
                }
            },
        }

        # JSON FILE DOWNLOAD
        if request.data.get("format") == "json":
            json_file_path = os.path.join(EXPORT_DIR, f"{user.username}_dashboard.json")
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return Response(
                {"status": "success", "message": "JSON file successfully saved.", "file_path": json_file_path},
                status=status.HTTP_200_OK,
            )

        # Check format
        if request.data.get("format", "").lower() == "pdf":
            export_type = request.data.get("export_type", "").lower()  # dashboard, carpool, booking
            pdf_file_path = os.path.join(EXPORT_DIR, f"{user.username}_dashboard.pdf")

            # Validate export type
            if export_type not in ["dashboard", "carpool", "booking"]:
                return Response(
                    {"status": "error", "message": "Invalid export_type. Use 'dashboard', 'carpool', or 'booking'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if export_type == "carpool" and not carpools.exists():
                return Response({"status": "error", "message": "No carpool data found for this filter."}, status=status.HTTP_404_NOT_FOUND)
            if export_type == "booking" and not bookings.exists():
                return Response({"status": "error", "message": "No booking data found for this filter."}, status=status.HTTP_404_NOT_FOUND)
            if export_type == "dashboard" and not (carpools.exists() or bookings.exists()):
                return Response({"status": "error", "message": "No data found for this filter."}, status=status.HTTP_404_NOT_FOUND)

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            elements.append(Paragraph(f"User Dashboard Report - {user.username}", styles['Title']))
            elements.append(Spacer(1, 12))

            # Overview
            overview_data = [
                ["User ID", "User", "Total Carpools", "Total Bookings", "Total Earning"],
                [user.user_id, user.first_name, dashboard.total_carpools, dashboard.total_bookings, str(dashboard.total_earning)]
            ]
            overview_table = Table(overview_data, colWidths=[70, 100, 100, 100, 100])
            overview_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            elements.append(Paragraph("Overview", styles['Heading2']))
            elements.append(overview_table)
            elements.append(Spacer(1, 20))

            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontSize=8,
                leading=9,
                alignment=1,
            )

            # CARPOOL TABLE
            if carpools.exists() and export_type in ["carpool", "dashboard"]:
                carpool_data = [["ID", "Start", "End", "Departure", "Arrival", "Status", "Bookings"]]
                for c in carpools:
                    carpool_data.append([
                        Paragraph(str(c.createcarpool_id), cell_style),
                        Paragraph(c.start_location, cell_style),
                        Paragraph(c.end_location, cell_style),
                        Paragraph(c.departure_time.strftime("%Y-%m-%d %H:%M") if c.departure_time else "-", cell_style),
                        Paragraph(c.arrival_time.strftime("%Y-%m-%d %H:%M") if c.arrival_time else "-", cell_style),
                        Paragraph(c.carpool_ride_status, cell_style),
                        Paragraph(str(c.bookings.count()), cell_style)
                    ])

                col_widths = [1.2*cm, 4.5*cm, 4.5*cm, 2.5*cm, 2.5*cm, 2*cm, 1.8*cm]
                carpool_table = Table(carpool_data, colWidths=col_widths, repeatRows=1)
                carpool_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                elements.append(Paragraph("Carpools", styles['Heading2']))
                elements.append(carpool_table)
                elements.append(Spacer(1, 20))

            # BOOKING TABLE 
            if bookings.exists() and export_type in ["booking", "dashboard"]:
                booking_data = [["ID", "Role", "Carpool ID", "Start", "End", "Status"]]
                for b in bookings:
                    booking_data.append([
                        Paragraph(str(b.booking_id), cell_style),
                        Paragraph(user.role, cell_style),
                        Paragraph(str(b.carpool_driver_name.createcarpool_id) if b.carpool_driver_name else "-", cell_style),
                        Paragraph(b.pickup_location or "-", cell_style),
                        Paragraph(b.drop_location or "-", cell_style),
                        Paragraph(b.booking_status, cell_style)
                    ])

                col_widths = [1.2*cm, 2.2*cm, 2.2*cm, 4.2*cm, 4.2*cm, 2.8*cm]
                booking_table = Table(booking_data, colWidths=col_widths, repeatRows=1)
                booking_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.green),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('WORDWRAP', (0, 0), (-1, -1), True),
                ]))
                elements.append(Paragraph("Bookings", styles['Heading2']))
                elements.append(booking_table)

            if len(elements) <= 4:
                return Response({"status": "error","message": "No valid data found for this export type."}, status=status.HTTP_400_BAD_REQUEST)

            doc.build(elements)
            with open(pdf_file_path, "wb") as f:
                f.write(buffer.getvalue())

            return Response({
                "status": "success",
                "message": f"PDF report generated successfully for {export_type} with applied filters.",
                "file_path": pdf_file_path,
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "carpool_status": carpool_status,
                    "booking_status": booking_status,
                }
            })

        return Response(data)

    except User.DoesNotExist:
        return Response({"status": "error", "message": "User not found."}, status=status.HTTP_404_NOT_FOUND)
