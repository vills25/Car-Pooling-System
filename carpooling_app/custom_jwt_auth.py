# custom_jwt_auth.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions
from rest_framework.permissions import BasePermission
from .models import User

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            if not user:
                raise exceptions.AuthenticationFailed('Access Token is expired.')
            return (user, validated_token)
        except Exception as e:
            raise exceptions.AuthenticationFailed(str(e))

    def get_user(self, validated_token):
        try:
            user_id = validated_token['user_id']
            user = User.objects.get(user_id=user_id)
            return user
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found', code='user_not_found')
        except KeyError:
            raise exceptions.AuthenticationFailed('Invalid token')


# Custom Permission Classes
class IsAuthenticatedCustom(BasePermission):
    """
    Custom permission class that works with your User model
    """
    def has_permission(self, request, view):
        # Simply check if user exists in request (set by our authentication)
        return bool(request.user and hasattr(request.user, 'user_id'))


class IsAdminCustom(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            hasattr(request.user, 'user_id') and 
            hasattr(request.user, 'role') and
            request.user.role == "admin"
        )


class IsDriverCustom(BasePermission):
    """
    Allows access only to driver users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            hasattr(request.user, 'user_id') and 
            hasattr(request.user, 'role') and
            request.user.role == "driver"
        )


class IsPassengerCustom(BasePermission):
    """
    Allows access only to passenger users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            hasattr(request.user, 'user_id') and 
            hasattr(request.user, 'role') and
            request.user.role == "passenger"
        )


class IsAdminOrDriverCustom(BasePermission):
    """
    Allows access to both admin and driver users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            hasattr(request.user, 'user_id') and 
            hasattr(request.user, 'role') and
            request.user.role in ["admin", "driver"]
        )


class IsAdminOrPassengerCustom(BasePermission):
    """
    Allows access to both admin and passenger users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            hasattr(request.user, 'user_id') and 
            hasattr(request.user, 'role') and
            request.user.role in ["admin", "passenger"]
        )


class IsDriverOrPassengerCustom(BasePermission):
    """
    Allows access to both driver and passenger users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            hasattr(request.user, 'user_id') and 
            hasattr(request.user, 'role') and
            request.user.role in ["driver", "passenger"]
        )


# Utility function to get tokens for user
def get_tokens_for_user(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['user_id'] = user.user_id
    refresh['username'] = user.username
    refresh['role'] = user.role
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }