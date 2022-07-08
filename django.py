from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializer import (
    UserActivitySerializer,
    UserCreationSerializer,
    MyTokenObtainPairSerializer
)


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class UserCreate(APIView):

    def post(self, request, format='json'):
        serializer = UserCreationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            if user:
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutAndBlacklistRefreshTokenForUserView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data["refresh_token"]

        if not refresh_token:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        RefreshToken(refresh_token).blacklist()

        return Response(status=status.HTTP_205_RESET_CONTENT)


class UserActivity(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, requset):
        serializer = UserActivitySerializer(requset.user)

        return Response(data=serializer.data, status=status.HTTP_200_OK)
