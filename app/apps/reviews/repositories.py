"""
Repositório de Avaliações — acesso centralizado ao banco para as avaliações embarcadas em Restaurante.
"""
from __future__ import annotations

from datetime import datetime, timezone
from bson import ObjectId

from apps.core.base_repository import PaginatedResult
from apps.reviews.documents import Avaliacao
from apps.restaurants.documents import Restaurante


class RepositorioAvaliacao:
    """Repositório para consultas nas avaliações embarcadas em Restaurante."""

    def buscar_por_cliente_e_pedido(self, cliente_id: str, pedido_id: str) -> Avaliacao | None:
        """Verifica se o cliente já avaliou um pedido específico."""
        try:
            restaurante = Restaurante.objects(
                avaliacoes__cliente_id=ObjectId(cliente_id),
                avaliacoes__pedido_id=ObjectId(pedido_id)
            ).first()
        except Exception:
            return None

        if restaurante:
            for av in restaurante.avaliacoes:
                if str(av.cliente_id) == cliente_id and str(av.pedido_id) == pedido_id:
                    return av
        return None

    def listar_por_restaurante(
        self, restaurante_id: str, page: int = 1, page_size: int = 10,
    ) -> PaginatedResult:
        """Lista avaliações de um restaurante, mais recentes primeiro."""
        try:
            restaurante = Restaurante.objects(id=ObjectId(restaurante_id)).first()
        except Exception:
            restaurante = None

        if not restaurante or not restaurante.avaliacoes:
            return PaginatedResult(results=[], count=0, page=page, total_pages=1, page_size=page_size)

        # Ordena em memória por criado_em desc (mais recentes primeiro)
        fallback_min = datetime.min.replace(tzinfo=timezone.utc)
        avaliacoes_sorted = sorted(
            restaurante.avaliacoes,
            key=lambda x: x.criado_em if x.criado_em else fallback_min,
            reverse=True
        )

        total = len(avaliacoes_sorted)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size

        paginated_items = avaliacoes_sorted[offset:offset+page_size]
        results = [av.to_dict() for av in paginated_items]

        return PaginatedResult(
            results=results,
            count=total,
            page=page,
            total_pages=total_pages,
            page_size=page_size,
        )

    def obter_avaliacao_restaurante(self, restaurante_id: str) -> dict:
        """Calcula a nota média de um restaurante em memória."""
        try:
            restaurante = Restaurante.objects(id=ObjectId(restaurante_id)).first()
        except Exception:
            restaurante = None

        if not restaurante or not restaurante.avaliacoes:
            return {'media': 0.0, 'contagem': 0}

        notas = [av.nota for av in restaurante.avaliacoes]
        contagem = len(notas)
        media = round(sum(notas) / contagem, 1) if contagem > 0 else 0.0
        return {
            'media': media,
            'contagem': contagem,
        }
