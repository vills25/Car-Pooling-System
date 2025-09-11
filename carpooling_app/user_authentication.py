import random
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from carpooling_app.custom_jwt_auth import IsAuthenticatedCustom
from .models import *
from .serializers import *
from django.db import transaction
from django.contrib.auth.hashers import make_password
from .custom_jwt_auth import IsAuthenticatedCustom

# Save activity log
def activity(user, details):
    try:
        Activity.objects.create(user=user, details=details)
    except Exception as e:
        print("Activity log failed:", str(e))

# Generate random OTP (6 digit)
def generate_otp():
    return str(random.randint(100000, 999999))

# Send OTP email
def send_otp_email(email, otp):
    subject = "Your OTP Code"
    message = f"Your OTP for password reset is: {otp}. It will expire in 10 minutes."
    from_email = "vishalsohaliya25@gmail.com"
    try:
        send_mail(subject, message, from_email, [email])
        return True
    except Exception as e:
        print("Email send failed:", str(e))
        return False

## Register(Sign-Up)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    data = request.data

    enter_username = data.get('username')
    enter_first_name = data.get('first_name')
    enter_last_name = data.get('last_name')
    enter_email = data.get('email')
    enter_password = make_password(data["password"])
    enter_phone_number = data.get('phone_number')
    enter_role = data.get('role','Passenger')
    enter_address = data.get('address')

    if not data.get("username") or not data.get("email") or not data.get("password"):
        return Response({"status":"fail","message":"username, email, password required"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=data["username"]).exists():
        return Response({"status":"fail","message":"Username already exist, try some diffrent username."}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(email=data["email"]).exists():
        return Response({"status":"fail","message":"Email already registered"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            user = User.objects.create(
                username = enter_username,
                first_name = enter_first_name,
                last_name = enter_last_name,
                email = enter_email,
                password = enter_password,
                phone_number = enter_phone_number,
                role = enter_role,
                address = enter_address,
                is_active = True
            )
            activity(user, f"User registered with username {user.username}")
            serializer = UserSerializer(user)
            return Response({"status":"success","message":"User registered successfully","User":serializer.data}, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({"status":"error","message":str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Login(Sign-In)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    username = request.data.get("username")
    password = request.data.get("password")

    try:
        user = User.objects.get(username=username)

        if not check_password(password, user.password):
            return Response({"status":"fail","message":"Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        
        user_data = {"user_id": user.user_id, "username": user.username, "first_name": user.first_name,}

        if user:

            refresh = RefreshToken()
            refresh['user_id'] = user.user_id
            refresh['username'] = user.username

            activity(user, f"{user.username} logged in")

        return Response({
            "status": "success",
            "message": "Login successful",
            "data":{
                "User": user_data,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            }
        }, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({"status":"fail","message":"User not found"}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status= status.HTTP_400_BAD_REQUEST)


## View profile data
@api_view(['POST'])
@permission_classes([IsAuthenticatedCustom])
def view_profile(request):

    user = request.data.get("user_id")

    user = User.objects.filter(user_id=user).first()
    try:
        if not user:
            return Response({"status":"fail", "message":"user not found/exist"}, status= status.HTTP_404_NOT_FOUND)
        
        serializer_data = UserSerializer(user)

        return Response({
            "status":"success", 
            "message":"user profile data fetched",
                "data":{
                    "User": serializer_data.data
                    }
            }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticatedCustom])
def update_profile(request):
    try:

        user = request.user
        request_data = request.data

        with transaction.atomic():
            if 'username' in request_data:
                if User.objects.filter(username=request_data['username']).exclude(user_id=user.user_id).exists():
                    return Response({"status":"fail", "message": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)
                user.username = request_data['username']

            if 'email' in request_data:
                if User.objects.filter(email=request_data['email']).exclude(user_id=user.user_id).exists():
                    return Response({"status":"fail", "message": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)
                user.email = request_data['email']

            if 'password' in request_data:
                user.password = make_password(request_data['password'])

            if 'first_name' in request_data:
                user.first_name = request_data['first_name']

            if 'last_name' in request_data:
                user.last_name = request_data['last_name']

            if 'phone_number' in request_data:
                user.phone_number = request_data['phone_number']

            if 'address' in request_data:
                user.address = request_data['address']

            if request.FILES.get('profile_pic'):
                user.profile_pic = request.FILES['profile_pic']

            user.save()

            activity(user, f"{user.username} updated his profile")
            serializer = UserSerializer(user, context={'request': request})
            return Response({"status":"success", "message":"Profile updated", "Updated User Data": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['DELETE'])
@permission_classes([IsAuthenticatedCustom])
def delete_profile(request):

    user_id = request.data.get('user_id')

    if not user_id:
        return Response({"status":"fail", "message": "enter user_id please"}, status=status.HTTP_400_BAD_REQUEST)
    
    if not request.user.is_superuser and request.user.user_id != user_id:
        return Response({"status":"fail", "message": "you can not delete others profile"}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(user_id = user_id)
        user.delete()

        activity(request.user, f"{request.user.username} deleted his profile: {user.username}")
        return Response({"status":"success", "message": "User deleted"}, status=status.HTTP_200_OK)
    
    except User.DoesNotExist:
        return Response({"status":"fail", "message": "User not found"}, status= status.HTTP_404_NOT_FOUND)

## FORGOT password view
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    
    email = request.data.get("email")

    if not email:
        return Response({"status":"fail","message":"email required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(email=email)
        otp = generate_otp()
        request.session["reset_email"] = email
        request.session["reset_otp"] = otp
        request.session["reset_time"] = str(timezone.now())
        send_otp_email(email, otp)
        return Response({"status":"success","message":"OTP sent to email"}, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({"status":"fail","message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

## RESET password
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    email = request.data.get("email")
    otp = request.data.get("otp")
    new_password = request.data.get("new_password")

    if not email or not otp or not new_password:
        return Response({"status":"fail","message":"email, otp, new_password required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if request.session.get("reset_email") != email or request.session.get("reset_otp") != otp:
            return Response({"status":"fail","message":"Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.get(email=email)
        user.password = make_password(new_password)
        user.save()
        return Response({"status":"success","message":"Password reset successfully"}, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({"status":"fail","message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

