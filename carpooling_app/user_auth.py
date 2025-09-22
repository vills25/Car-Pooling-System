import email
from tkinter import PhotoImage
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.hashers import make_password
from .models import *
from .serializers import *
from .custom_jwt_auth import IsAuthenticatedCustom
from .utils import activity, send_otp_email, generate_otp, send_contact_email

## Register User (Sign-Up)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new user.

        Parameters:
        username (str): required, username of the user
        first_name (str): required, first name of the user
        last_name (str): required, last name of the user
        email (str): required, email of the user
        password (str): required, password of the user
        phone_number (str): required, phone number of the user
        role (str): optional, role of the user, default is Passenger
        address (str): optional, address of the user
        gender (str): optional, gender of the user

    Returns:
    Response: a json response with the status, message and the user data
    """
    enter_username = request.data.get('username')
    enter_first_name = request.data.get('first_name')
    enter_last_name = request.data.get('last_name')
    enter_email = request.data.get('email')
    enter_phone_number = request.data.get('phone_number')
    enter_role = request.data.get('role','Passenger')
    enter_address = request.data.get('address')
    enter_gender = request.data.get('gender')

    if not request.data.get("username") or not request.data.get("email") or not request.data.get("password") or not request.data.get("confirm_password"):
        return Response({"status":"fail","message":"username, email, password required"}, status=status.HTTP_400_BAD_REQUEST)

    raw_password = request.data.get("password")
    enter_confirm_password = request.data.get("confirm_password")

    if raw_password != enter_confirm_password:
        return Response({"status":"fail","message":"Password and confirm password do not match"}, status=status.HTTP_400_BAD_REQUEST)

    enter_password = make_password(raw_password)

    if User.objects.filter(username=request.data["username"]).exists():
        return Response({"status":"fail","message":"Username already exist, try some diffrent username."}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(email=request.data["email"]).exists():
        return Response({"status":"fail","message":f"Email  with Email ID: {enter_email} already registered"}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(phone_number = request.data["phone_number"]).exists():
        return Response({"status":"fail", "message":f"user with phone number: {enter_phone_number} already registered"}, status=status.HTTP_400_BAD_REQUEST)

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
                gender = enter_gender,
                is_active = True
            )
            activity(user, f"User registered with username {user.username}")
            serializer = UserSerializer(user)
            return Response({"status":"success","message":"User registered successfully","User":serializer.data}, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({"status":"error","message":str(e)}, status=status.HTTP_400_BAD_REQUEST)

## Login User (Sign-In)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """
    Login user.

    Parameters:
    username (str): required, username of the user
    password (str): required, password of the user

    Returns:
    Response: a json response with the status, message, access token and refresh token
    If the login is successful, it will return a 200 status code with a success message and the access token and refresh token.
    If the login fails, it will return a 401 status code with an invalid credentials message.
    If the user is not found, it will return a 404 status code with an user not found message.
    """
    username = request.data.get("username/email/phone_number")
    password = request.data.get("password")

    try:
        user = User.objects.filter( Q(username=username) | Q(email=username) | Q(phone_number=username)).first()

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

## Logout User (Sign-Out) session based
@api_view(['POST'])
@permission_classes([IsAuthenticatedCustom])
def logout_user(request):

    """
    Logout user from the system.

    Parameters:
    request (HttpRequest): Request object passed in by the Django framework.
    refresh_token (str): The refresh token to blacklist.

    Returns:
    Response: A JSON response with the status, message and data.
    """
    user = request.user
    refresh_token = request.data.get('refresh_token')

    try:
        request.session.flush()
    except Exception as e:
        return Response({"status":"fail", "message":str(e)}, status=status.HTTP_400_BAD_REQUEST)

    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            activity(user, f"{user.username} logged out)")

        except Exception as e:
            return Response({"status": "success", "message": str(e)}, status=status.HTTP_200_OK)

    activity(user, f"{user.username} logged out")
    return Response({"status": "success", "message": "Logged out successfully"}, status=status.HTTP_200_OK)

## VIEW User profile data
@api_view(['GET'])
@permission_classes([IsAuthenticatedCustom])
def view_profile(request):

    """
    Fetch user profile data.

    Parameters:
    request (HttpRequest): Request object passed in by the Django framework.

    Returns:
    Response: A JSON response with the status, message and data.
    If the user is not found, it will return a 404 status code with an user not found message.
    If the user is found, it will return a 200 status code with a success message and the user profile data.
    If any error occurs, it will return a 400 status code with an error message.
    """
    user = request.user

    try:
        if not user:
            return Response({"status":"fail", "message":"user not found/exist"}, status= status.HTTP_404_NOT_FOUND)
        
        serializer_data = UserSerializer(user, context={'request': request})

        return Response({
            "status":"success", 
            "message":"user profile data fetched",
                "data":{
                    "User": serializer_data.data
                    }
            }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## UPDATE User profile view
@api_view(['PUT'])
@permission_classes([IsAuthenticatedCustom])
def update_profile(request):
    """
    Update the user profile data.

    Parameters:
    request (HttpRequest): Request object passed in by the Django framework.
    
    Returns:
    Response: A JSON response with the status, message and data.
    If the user is not found, it will return a 404 status code with an user not found message.
    If the user is found, it will return a 200 status code with a success message and the updated user profile data.
    If any error occurs, it will return a 400 status code with an error message.

    """
    try:
        user = request.user
        
        # Extract all input fields
        get_username = request.data.get('username')
        get_email = request.data.get('email')
        get_password = request.data.get('password')
        get_first_name = request.data.get('first_name')
        get_last_name = request.data.get('last_name')
        get_phone_number = request.data.get('phone_number')
        get_address = request.data.get('address')
        get_role = request.data.get('role')
        get_profile_pic = request.FILES.get('profile_pic')
        get_gender = request.data.get('gender')

        with transaction.atomic():
            if get_username is not None:
                if User.objects.filter(username=get_username).exclude(user_id=user.user_id).exists():
                    return Response({"status":"fail", "message": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)
                user.username = get_username

            if get_email is not None:
                if User.objects.filter(email=get_email).exclude(user_id=user.user_id).exists():
                    return Response({"status":"fail", "message": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)
                user.email = get_email

            if get_password is not None:
                user.password = make_password(get_password)

            if get_first_name is not None:
                user.first_name = get_first_name

            if get_last_name is not None:
                user.last_name = get_last_name

            if get_phone_number is not None:
                user.phone_number = get_phone_number

            if get_address is not None:
                user.address = get_address

            if get_role is not None:
                user.role = get_role

            if get_gender is not None:
                user.gender = get_gender

            if get_profile_pic is not None:
                user.profile_pic = get_profile_pic

            user.save()

            activity(user, f"{user.username} updated his profile")
            serializer = UserSerializer(user, context={'request': request})
            return Response({"status":"success", "message":"Profile updated", "Updated User Data": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status":"error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

## DELETE User profile view    
@api_view(['DELETE'])
@permission_classes([IsAuthenticatedCustom])
def delete_profile(request):

    """
    Delete a user profile.

    This API will delete a user profile.
    It will only delete the profile if the user is the creator of the profile or an admin.

    Parameters:
    user_id: int (required)

    Returns:
    A JSON response with the status, message and data of the deleted user.
    If the delete is successful, it will return a 200 status code with a success message and the deleted user details.
    If the delete fails, it will return a 400 status code with an error message and the error details.
    """
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

## FORGOT User password view
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    
    """
    Forgot Password View

    This API will send an OTP to the user's email id if the user exists.
    The OTP will be valid for 5 minutes.

    Parameters:
    email (str): required, email of the user

    Returns:
    Response: a json response with the status, message and data of the user.
    If the OTP is sent successfully, it will return a 200 status code with a success message and the email id of the user.
    If the OTP sending fails, it will return a 404 status code with an error message if the user is not found.
    """
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
        return Response({"status":"success","message":f"OTP sent to email id: {email}"}, status=status.HTTP_200_OK)
    
    except User.DoesNotExist:
        return Response({"status":"fail","message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

## RESET User password
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Resets the password of the user.

    Parameters:
    email (str): required, email of the user
    otp (str): required, OTP sent to the user's email id
    new_password (str): required, new password of the user
    confirm_new_password (str): required, confirm new password of the user

    Returns:
    Response: a json response with the status, message and data of the user.
    If the password reset is successful, it will return a 200 status code with a success message and the email id of the user.
    If the password reset fails, it will return a 404 status code with an error message if the user is not found, or a 400 status code with an error message if the OTP is invalid.
    """
    email = request.data.get("email")
    otp = request.data.get("otp")
    raw_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_new_password")
    new_password = check_password(raw_password, confirm_password)

    if not email or not otp or not new_password:
        return Response({"status":"fail","message":"email, otp, new_password required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if request.session.get("reset_email") != email or request.session.get("reset_otp") != otp:
            return Response({"status":"fail","message":"Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.get(email=email)

        if raw_password != confirm_password:
            return Response({"status":"fail","message":"Password and confirm password not matched"}, status=status.HTTP_400_BAD_REQUEST)
        user.password = make_password(new_password)
        user.save()
        return Response({"status":"success","message":"Password reset successfully"}, status=status.HTTP_200_OK)
    
    except User.DoesNotExist:
        return Response({"status":"fail","message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"status":"fail","message":str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
## contact us form
@api_view(['POST'])
@permission_classes([AllowAny])
def contact_us(request):
    """
    Contact us view using Contact model, Visitor Enquiry, send all fields detail in emails too.
    
    Parameters:
    name, email, phone_number and your_message required in str format
    
    Returns:
    Response: a json response with the status, message and data of the contact form.
    If the contact form submission is successful, it will return a 200 status code with a success message.
    If the contact form submission fails, it will return a 400 status code with an error message and the error details.
    """
    name = request.data.get("name")
    email = request.data.get("email")
    phone_number = request.data.get("phone_number")
    your_message = request.data.get("your_message")

    if not name or not email or not phone_number or not your_message:
        return Response({"status":"fail","message":"name, email, phone_number, message required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        contact = Contact.objects.create(name=name, email=email, phone_number=phone_number, your_message=your_message)
        contact.save()
        send_contact_email(name, email, phone_number, your_message)
        return Response({"status":"success","message":"contact form submitted successfully"}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"status":"error","message":str(e)}, status=status.HTTP_400_BAD_REQUEST)
