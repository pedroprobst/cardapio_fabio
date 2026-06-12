"""
Documentos MongoEngine para a coleção de Pedidos (orders).
Schema conforme doc 06-modelagem-mongodb.md.
"""
from datetime import datetime, timezone
import mongoengine as me


class ItemPedido(me.EmbeddedDocument):
    """Item do pedido — snapshot do produto no momento do pedido."""
    produto_id = me.ObjectIdField(required=True)
    nome = me.StringField(required=True)
    preco = me.DecimalField(required=True, precision=2)
    quantidade = me.IntField(required=True, min_value=1, max_value=99)
    subtotal = me.DecimalField(required=True, precision=2)
    imagem_url = me.StringField()
    # INCREMENTO: Campo para armazenar os adicionais escolhidos
    extras = me.ListField(me.DictField(), default=list)

    meta = {'strict': False}


class MudancaStatus(me.EmbeddedDocument):
    """Registro de uma transição de status."""
    status = me.StringField(required=True)
    alterado_em = me.DateTimeField(default=lambda: datetime.now(timezone.utc))
    alterado_por = me.ObjectIdField()
    meta = {'strict': False}


class EnderecoEntrega(me.EmbeddedDocument):
    """Snapshot do endereço de entrega."""
    rua = me.StringField(max_length=200)
    numero = me.StringField(max_length=20)
    complemento = me.StringField(max_length=100)
    bairro = me.StringField(max_length=100)
    cidade = me.StringField(max_length=100)
    estado = me.StringField(max_length=2)
    cep = me.StringField(max_length=10)
    meta = {'strict': False}


OPCOES_STATUS = ('pendente', 'confirmado', 'preparando', 'pronto', 'entregue', 'cancelado')


class SubPedido(me.EmbeddedDocument):
    """Sub-pedido para um restaurante específico dentro de um pedido multi-restaurante."""
    restaurante_id = me.ObjectIdField(required=True)
    itens = me.EmbeddedDocumentListField(ItemPedido, required=True)
    total = me.DecimalField(required=True, precision=2, min_value=0)
    taxa_entrega = me.DecimalField(default=0, precision=2)
    valor_desconto = me.DecimalField(default=0, precision=2)
    codigo_cupom = me.StringField(max_length=30)
    status = me.StringField(required=True, choices=OPCOES_STATUS, default='pendente')
    historico_status = me.EmbeddedDocumentListField(MudancaStatus, default=list)
    meta = {'strict': False}


class Pedido(me.Document):
    """Documento de pedido armazenado na coleção MongoDB 'pedidos'."""
    OPCOES_STATUS = OPCOES_STATUS
    OPCOES_ENTREGA = ('entrega', 'retirada')
    OPCOES_PAGAMENTO = ('pix', 'cartao', 'dinheiro')

    # Transições de status válidas
    TRANSICOES_VALIDAS = {
        'pendente': ['confirmado', 'cancelado'],
        'confirmado': ['preparando', 'cancelado'],
        'preparando': ['pronto', 'cancelado'],
        'pronto': ['entregue', 'cancelado'],
        'entregue': [],
        'cancelado': [],
    }

    numero_pedido = me.StringField(required=True, unique=True)
    cliente_id = me.ObjectIdField(required=True)
    restaurante_id = me.ObjectIdField(required=False)
    itens = me.EmbeddedDocumentListField(ItemPedido, required=False)
    sub_pedidos = me.EmbeddedDocumentListField(SubPedido, default=list)
    total = me.DecimalField(required=True, precision=2, min_value=0)
    taxa_entrega = me.DecimalField(default=0, precision=2)
    valor_desconto = me.DecimalField(default=0, precision=2)
    codigo_cupom = me.StringField(max_length=30)
    status = me.StringField(required=True, choices=OPCOES_STATUS, default='pendente')
    historico_status = me.EmbeddedDocumentListField(MudancaStatus, default=list)
    metodo_entrega = me.StringField(required=True, choices=OPCOES_ENTREGA)
    endereco_entrega = me.EmbeddedDocumentField(EnderecoEntrega)
    metodo_pagamento = me.StringField(required=True, choices=OPCOES_PAGAMENTO, default='pix')
    observacoes = me.StringField(max_length=500)
    criado_em = me.DateTimeField(default=lambda: datetime.now(timezone.utc))
    atualizado_em = me.DateTimeField(default=lambda: datetime.now(timezone.utc))

    meta = {
        'collection': 'pedidos',
        'indexes': [
            {'fields': ['numero_pedido'], 'unique': True},
            {'fields': ['cliente_id', '-criado_em']},
            {'fields': ['restaurante_id', 'status', '-criado_em']},
            {'fields': ['sub_pedidos.restaurante_id', 'sub_pedidos.status', '-criado_em']},
            {'fields': ['status']},
            {'fields': ['-criado_em']},
        ],
        'ordering': ['-criado_em'],
        'strict': False,
    }

    def save(self, *args, **kwargs):
        self.atualizado_em = datetime.now(timezone.utc)
        return super().save(*args, **kwargs)

    def to_dict(self):
        return {
            'id': str(self.id),
            'numero_pedido': self.numero_pedido,
            'cliente_id': str(self.cliente_id),
            'restaurante_id': str(self.restaurante_id) if self.restaurante_id else None,
            'itens': [
                {
                    'produto_id': str(item.produto_id),
                    'nome': item.nome,
                    'preco': float(item.preco),
                    'quantidade': item.quantidade,
                    'subtotal': float(item.subtotal),
                    'imagem_url': item.imagem_url,
                    # INCREMENTO: Adicionado para o Front-end mostrar os nomes dos extras
                    'extras': item.extras,
                }
                for item in self.itens
            ] if self.itens else [],
            'sub_pedidos': [
                {
                    'restaurante_id': str(sp.restaurante_id),
                    'itens': [
                        {
                            'produto_id': str(item.produto_id),
                            'nome': item.nome,
                            'preco': float(item.preco),
                            'quantidade': item.quantidade,
                            'subtotal': float(item.subtotal),
                            'imagem_url': item.imagem_url,
                            'extras': item.extras,
                        }
                        for item in sp.itens
                    ],
                    'total': float(sp.total),
                    'taxa_entrega': float(sp.taxa_entrega) if sp.taxa_entrega else 0,
                    'valor_desconto': float(sp.valor_desconto) if sp.valor_desconto else 0,
                    'codigo_cupom': sp.codigo_cupom,
                    'status': sp.status,
                    'historico_status': [
                        {
                            'status': hs.status,
                            'alterado_em': hs.alterado_em.isoformat() if hs.alterado_em else None,
                            'alterado_por': str(hs.alterado_por) if hs.alterado_por else None,
                        }
                        for hs in sp.historico_status
                    ]
                }
                for sp in self.sub_pedidos
            ] if self.sub_pedidos else [],
            'total': float(self.total),
            'taxa_entrega': float(self.taxa_entrega) if self.taxa_entrega else 0,
            'valor_desconto': float(self.valor_desconto) if self.valor_desconto else 0,
            'codigo_cupom': self.codigo_cupom,
            'status': self.status,
            'historico_status': [
                {
                    'status': hs.status,
                    'alterado_em': hs.alterado_em.isoformat() if hs.alterado_em else None,
                    'alterado_por': str(hs.alterado_por) if hs.alterado_por else None,
                }
                for hs in self.historico_status
            ],
            'metodo_entrega': self.metodo_entrega,
            'endereco_entrega': {
                'rua': self.endereco_entrega.rua,
                'numero': self.endereco_entrega.numero,
                'complemento': self.endereco_entrega.complemento,
                'bairro': self.endereco_entrega.bairro,
                'cidade': self.endereco_entrega.cidade,
                'estado': self.endereco_entrega.estado,
                'cep': self.endereco_entrega.cep,
            } if self.endereco_entrega else None,
            'metodo_pagamento': self.metodo_pagamento,
            'observacoes': self.observacoes,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None,
        }