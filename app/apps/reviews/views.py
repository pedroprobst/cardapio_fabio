"""
Views da API de Avaliações.
"""
from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.core.authentication import JWTAuthentication
from apps.reviews.serializers import CreateReviewSerializer
from apps.reviews.services import ReviewService


class ReviewListView(APIView):
    def get(self, request):
        """Lista avaliações para um restaurante (público)."""
        restaurant_id = request.query_params.get('restaurant_id')
        if not restaurant_id:
            return Response(
                {'error': 'restaurant_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        service = ReviewService()
        page = int(request.query_params.get('page', 1))
        result = service.list_restaurant_reviews(restaurant_id, page=page)
        return Response(result)

    def post(self, request):
        """Cria uma avaliação (cliente autenticado)."""
        auth = JWTAuthentication()
        user_auth = auth.authenticate(request)
        if not user_auth:
            return Response(
                {'error': 'Autenticação necessária.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = user_auth[0]

        serializer = CreateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = ReviewService()
        result = service.create_review(
            customer_id=str(user.id),
            customer_name=user.nome,
            **serializer.validated_data,
        )
        return Response(result, status=status.HTTP_201_CREATED)


class MyReviewView(APIView):
    """Retorna a avaliação existente do usuário para um pedido específico."""

    def get(self, request):
        """GET /api/reviews/my-review/?pedido_id=<id>"""
        auth = JWTAuthentication()
        user_auth = auth.authenticate(request)
        if not user_auth:
            return Response(
                {'error': 'Autenticação necessária.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = user_auth[0]

        pedido_id = request.query_params.get('pedido_id')
        if not pedido_id:
            return Response(
                {'error': 'pedido_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = ReviewService()
        review = service.get_user_review_for_order(
            customer_id=str(user.id),
            pedido_id=pedido_id,
        )

        if review:
            return Response(review)
        return Response({'exists': False}, status=status.HTTP_404_NOT_FOUND)
