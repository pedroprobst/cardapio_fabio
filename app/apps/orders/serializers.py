"""Serializers de Pedidos para DRF."""
from __future__ import annotations

from rest_framework import serializers


class ItemPedidoSerializer(serializers.Serializer):
    """Valida itens individuais do pedido."""
    produto_id = serializers.CharField()
    quantidade = serializers.IntegerField(min_value=1, max_value=99)
    extras = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class SubPedidoSerializer(serializers.Serializer):
    """Valida dados de um sub-pedido de um restaurante no checkout múltiplo."""
    restaurante_id = serializers.CharField()
    itens = ItemPedidoSerializer(many=True, min_length=1)
    codigo_cupom = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')


class CriarPedidoSerializer(serializers.Serializer):
    """Valida dados de criação de pedido."""
    # Para pedidos individuais (compatibilidade legado)
    restaurante_id = serializers.CharField(required=False)
    itens = ItemPedidoSerializer(many=True, required=False)
    codigo_cupom = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')

    # Para pedidos multi-restaurante
    pedidos = SubPedidoSerializer(many=True, required=False)

    metodo_entrega = serializers.ChoiceField(choices=['entrega', 'retirada'])
    metodo_pagamento = serializers.ChoiceField(choices=['pix', 'cartao', 'dinheiro'], default='pix')
    observacoes = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    endereco_entrega = serializers.DictField(required=False)

    def validate_itens(self, value):
        """Validação dos itens do pedido."""
        if value is not None and not value:
            raise serializers.ValidationError("Pedido deve conter ao menos 1 item.")
        return value

    def validate(self, data):
        """Valida que endereço de entrega é informado para pedidos de entrega e se dados mínimos foram fornecidos."""
        pedidos = data.get('pedidos')
        restaurante_id = data.get('restaurante_id')
        itens = data.get('itens')

        if not pedidos and (not restaurante_id or not itens):
            raise serializers.ValidationError(
                "Deve fornecer a lista de 'pedidos' ou ('restaurante_id' e 'itens')."
            )

        if data.get('metodo_entrega') == 'entrega' and not data.get('endereco_entrega'):
            raise serializers.ValidationError(
                {'endereco_entrega': 'Endereço de entrega é obrigatório para delivery.'}
            )
        return data


class AtualizarStatusPedidoSerializer(serializers.Serializer):
    """Valida requisições de atualização de status."""
    status = serializers.ChoiceField(
        choices=['confirmado', 'preparando', 'pronto', 'entregue', 'cancelado']
    )
    motivo_cancelamento = serializers.CharField(max_length=500, required=False)

    def validate(self, data):
        if data['status'] == 'cancelado' and not data.get('motivo_cancelamento'):
            raise serializers.ValidationError(
                {'motivo_cancelamento': 'Motivo é obrigatório para cancelamento.'}
            )
        return data


class ValidarCupomSerializer(serializers.Serializer):
    """Valida requisições de validação de cupom."""
    restaurante_id = serializers.CharField()
    codigo = serializers.CharField()
    total_carrinho = serializers.DecimalField(max_digits=10, decimal_places=2)
