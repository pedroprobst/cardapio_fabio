"""
Serviço de Avaliações — lógica de negócio para avaliações de clientes.
"""
from __future__ import annotations

import logging

from bson import ObjectId

from apps.core.exceptions import ResourceNotFoundError
from apps.core.utils import sanitize_input
from apps.restaurants.repositories import RepositorioRestaurante
from apps.reviews.documents import Avaliacao
from apps.reviews.repositories import RepositorioAvaliacao

logger = logging.getLogger(__name__)


class ReviewService:
    """Serviço contendo toda a lógica de negócio de avaliações."""

    def __init__(
        self,
        review_repo: RepositorioAvaliacao | None = None,
        restaurant_repo: RepositorioRestaurante | None = None,
    ) -> None:
        self.repo = review_repo or RepositorioAvaliacao()
        self.restaurant_repo = restaurant_repo or RepositorioRestaurante()

    def create_review(
        self,
        customer_id: str,
        customer_name: str,
        restaurante_id: str,
        nota: int,
        comentario: str = '',
        pedido_id: str | None = None,
    ) -> dict:
        """Cria uma nova avaliação e atualiza a média do restaurante."""
        restaurante = self.restaurant_repo.find_by_id(restaurante_id)
        if not restaurante:
            raise ResourceNotFoundError('Restaurante')

        # Verifica se já existe avaliação deste cliente para este pedido no mesmo restaurante
        existing = None
        if pedido_id:
            for av in restaurante.avaliacao.avaliacoes:
                if str(av.cliente_id) == customer_id and str(av.pedido_id) == pedido_id:
                    existing = av
                    break

        if existing:
            # Atualiza a avaliação existente
            existing.nota = nota
            existing.comentario = sanitize_input(comentario) if comentario else ''
            avaliacao = existing
            logger.info("Avaliação atualizada: cliente=%s, restaurante=%s, nota=%d", customer_id, restaurante_id, nota)
        else:
            # Cria nova avaliação
            avaliacao = Avaliacao(
                cliente_id=ObjectId(customer_id),
                nome_cliente=sanitize_input(customer_name),
                restaurante_id=ObjectId(restaurante_id),
                pedido_id=ObjectId(pedido_id) if pedido_id else None,
                nota=nota,
                comentario=sanitize_input(comentario) if comentario else '',
            )
            restaurante.avaliacao.avaliacoes.append(avaliacao)
            logger.info("Avaliação criada: cliente=%s, restaurante=%s, nota=%d", customer_id, restaurante_id, nota)

        # Atualiza a nota e contagem do restaurante diretamente em memória
        notas = [av.nota for av in restaurante.avaliacao.avaliacoes]
        restaurante.avaliacao.media = round(sum(notas) / len(notas), 1) if notas else 0.0
        restaurante.avaliacao.contagem = len(notas)

        # Salva o restaurante, o que persiste as avaliações embarcadas
        self.restaurant_repo.save(restaurante)

        return avaliacao.to_dict()

    def list_restaurant_reviews(
        self, restaurant_id: str, page: int = 1, page_size: int = 10,
    ) -> dict:
        """Lista avaliações de um restaurante com paginação."""
        result = self.repo.listar_por_restaurante(restaurant_id, page=page, page_size=page_size)
        return result.to_dict()
