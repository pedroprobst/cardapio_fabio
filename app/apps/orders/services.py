"""
Serviço de Pedidos — lógica de negócio para pedidos.

Gerencia criação de pedidos (com snapshot de preços), transições
de status e notificações WebSocket.

Refatorado para usar:
- RepositorioPedido
- ValidadorCupom (DRY)
- Exceções de domínio
- Injeção de dependência
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from bson import ObjectId
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.core.enums import StatusPedido, MetodoEntrega
from apps.core.exceptions import InvalidStatusTransition, ResourceNotFoundError
from apps.core.utils import gerar_numero_pedido, sanitize_input
from apps.core.validators import CouponValidator
from apps.orders.documents import Pedido, ItemPedido, MudancaStatus, EnderecoEntrega
from apps.orders.repositories import RepositorioPedido
from apps.restaurants.documents import Restaurante
from apps.restaurants.repositories import RepositorioRestaurante

logger = logging.getLogger(__name__)


class ServicoPedido:
    """Serviço contendo toda a lógica de negócio de pedidos."""

    def __init__(
        self,
        repo_pedido: RepositorioPedido | None = None,
        repo_restaurante: RepositorioRestaurante | None = None,
    ) -> None:
        self.repo_pedido = repo_pedido or RepositorioPedido()
        self.repo_restaurante = repo_restaurante or RepositorioRestaurante()

    def criar_pedido(self, cliente_id: str, dados: dict) -> dict:
        if 'pedidos' in dados and dados['pedidos']:
            # Multi-restaurant checkout: registrar tudo em um UNICO documento
            from apps.orders.documents import SubPedido
            sub_pedidos_list = []
            todos_itens = []
            total_geral = Decimal('0.00')
            taxa_entrega_geral = Decimal('0.00')
            desconto_geral = Decimal('0.00')
            
            for sub_dados in dados['pedidos']:
                restaurante = self.repo_restaurante.buscar_ativo_por_id(sub_dados['restaurante_id'])
                if not restaurante:
                    continue
                
                # Processar itens do sub-pedido
                mapa_produtos = {str(p._id): p for p in restaurante.produtos}
                itens_pedido = []
                subtotal_pedido = Decimal('0.00')
                
                for item_dados in sub_dados['itens']:
                    produto = mapa_produtos.get(item_dados['produto_id'])
                    if not produto or not produto.esta_disponivel:
                        continue
                    
                    preco_unitario_final = Decimal(str(produto.preco))
                    extras_selecionados = item_dados.get('extras', [])
                    extras_para_salvar = []
                    
                    for extra in extras_selecionados:
                        nome_extra = str(extra.get('nome', '')).strip().lower()
                        ing_original = next(
                            (i for i in produto.ingredientes if i.nome.strip().lower() == nome_extra), 
                            None
                        )
                        
                        valor_extra = Decimal('0.00')
                        if ing_original:
                            valor_extra = Decimal(str(ing_original.preco))
                        else:
                            valor_extra = Decimal(str(extra.get('preco', 0)))

                        preco_unitario_final += valor_extra
                        extras_para_salvar.append({
                            'nome': ing_original.nome if ing_original else extra.get('nome'),
                            'preco': float(valor_extra)
                        })

                    quantidade = int(item_dados.get('quantidade', 1))
                    subtotal_item = preco_unitario_final * quantidade
                    
                    item_obj = ItemPedido(
                        produto_id=ObjectId(item_dados['produto_id']),
                        nome=produto.nome,
                        preco=preco_unitario_final,
                        quantidade=quantidade,
                        subtotal=subtotal_item,
                        imagem_url=produto.imagem_url,
                        extras=extras_para_salvar
                    )
                    itens_pedido.append(item_obj)
                    todos_itens.append(item_obj)
                    subtotal_pedido += subtotal_item
                
                # Calcular taxas e descontos do sub-pedido
                taxa_entrega = Decimal(str(restaurante.taxa_entrega or 0)) if dados['metodo_entrega'] == 'entrega' else Decimal('0')
                valor_desconto, codigo_cupom = CouponValidator.validate_and_calculate(
                    coupon_code=sub_dados.get('codigo_cupom', ''),
                    coupons=restaurante.cupons,
                    cart_total=subtotal_pedido,
                )
                
                sub_total_final = subtotal_pedido + taxa_entrega - valor_desconto
                
                sub_pedidos_list.append(SubPedido(
                    restaurante_id=ObjectId(sub_dados['restaurante_id']),
                    itens=itens_pedido,
                    total=sub_total_final,
                    taxa_entrega=taxa_entrega,
                    valor_desconto=valor_desconto,
                    codigo_cupom=codigo_cupom,
                    status=StatusPedido.PENDENTE,
                    historico_status=[MudancaStatus(
                        status=StatusPedido.PENDENTE,
                        alterado_em=datetime.now(timezone.utc),
                        alterado_por=ObjectId(cliente_id),
                    )]
                ))
                
                total_geral += sub_total_final
                taxa_entrega_geral += taxa_entrega
                desconto_geral += valor_desconto

            pedido = Pedido(
                numero_pedido=gerar_numero_pedido(),
                cliente_id=ObjectId(cliente_id),
                restaurante_id=None,
                itens=todos_itens,
                sub_pedidos=sub_pedidos_list,
                total=total_geral,
                taxa_entrega=taxa_entrega_geral,
                valor_desconto=desconto_geral,
                metodo_pagamento=dados.get('metodo_pagamento', 'pix'),
                status=StatusPedido.PENDENTE,
                historico_status=[MudancaStatus(
                    status=StatusPedido.PENDENTE,
                    alterado_em=datetime.now(timezone.utc),
                    alterado_por=ObjectId(cliente_id),
                )],
                metodo_entrega=dados['metodo_entrega'],
                endereco_entrega=dados.get('endereco_entrega') if dados['metodo_entrega'] == 'entrega' else None,
                observacoes=dados.get('observacoes', ''),
            )
            
            self.repo_pedido.salvar(pedido)
            return {
                'multi': True,
                'pedido': pedido.to_dict(),
                'numero_pedido': pedido.numero_pedido
            }
        else:
            # Single order
            return self._criar_pedido_individual(cliente_id, dados)

    def _criar_pedido_individual(self, cliente_id: str, dados: dict) -> dict:
        restaurante = self.repo_restaurante.buscar_ativo_por_id(dados['restaurante_id'])
        if not restaurante:
            raise ResourceNotFoundError('Restaurante')

        mapa_produtos = {str(p._id): p for p in restaurante.produtos}
        itens_pedido = []
        subtotal_pedido = Decimal('0.00')

        for item_dados in dados['itens']:
            produto = mapa_produtos.get(item_dados['produto_id'])
            if not produto or not produto.esta_disponivel:
                continue

            # Inicia com o preço base do produto
            preco_unitario_final = Decimal(str(produto.preco))
            extras_selecionados = item_dados.get('extras', [])
            extras_para_salvar = []
            
            for extra in extras_selecionados:
                # Normalização para busca: remove espaços e ignora case
                nome_extra = str(extra.get('nome', '')).strip().lower()
                
                # Busca o ingrediente original no banco para validar o preço real
                ing_original = next(
                    (i for i in produto.ingredientes if i.nome.strip().lower() == nome_extra), 
                    None
                )
                
                valor_extra = Decimal('0.00')
                if ing_original:
                    valor_extra = Decimal(str(ing_original.preco))
                else:
                    # Fallback de segurança caso o ingrediente tenha sido removido do cardápio após ir pro carrinho
                    valor_extra = Decimal(str(extra.get('preco', 0)))

                preco_unitario_final += valor_extra
                extras_para_salvar.append({
                    'nome': ing_original.nome if ing_original else extra.get('nome'),
                    'preco': float(valor_extra)
                })

            quantidade = int(item_dados.get('quantidade', 1))
            subtotal_item = preco_unitario_final * quantidade

            # Criando o Snapshot do Item com o PREÇO FINAL JÁ SOMADO
            itens_pedido.append(ItemPedido(
                produto_id=ObjectId(item_dados['produto_id']),
                nome=produto.nome,
                preco=preco_unitario_final, # Este é o campo que deve ser R$ 28,99
                quantidade=quantidade,
                subtotal=subtotal_item,
                imagem_url=produto.imagem_url,
                extras=extras_para_salvar
            ))
            subtotal_pedido += subtotal_item

        # Taxa de entrega e descontos...
        taxa_entrega = Decimal(str(restaurante.taxa_entrega or 0)) if dados['metodo_entrega'] == 'entrega' else Decimal('0')
        
        # (Lógica de cupom omitida para brevidade, mas mantida no seu original)
        valor_desconto, codigo_cupom = CouponValidator.validate_and_calculate(
            coupon_code=dados.get('codigo_cupom', ''),
            coupons=restaurante.cupons,
            cart_total=subtotal_pedido,
        )

        total_final = subtotal_pedido + taxa_entrega - valor_desconto

        pedido = Pedido(
            numero_pedido=gerar_numero_pedido(),
            cliente_id=ObjectId(cliente_id),
            restaurante_id=ObjectId(dados['restaurante_id']),
            itens=itens_pedido,
            total=total_final,
            taxa_entrega=taxa_entrega,
            valor_desconto=valor_desconto,
            codigo_cupom=codigo_cupom,
            metodo_pagamento=dados.get('metodo_pagamento', 'pix'),
            status=StatusPedido.PENDENTE,
            historico_status=[MudancaStatus(
                status=StatusPedido.PENDENTE,
                alterado_em=datetime.now(timezone.utc),
                alterado_por=ObjectId(cliente_id),
            )],
            metodo_entrega=dados['metodo_entrega'],
            endereco_entrega=dados.get('endereco_entrega') if dados['metodo_entrega'] == 'entrega' else None,
            observacoes=dados.get('observacoes', ''),
        )
        
        self.repo_pedido.salvar(pedido)
        return pedido.to_dict()

    def atualizar_status(
        self,
        pedido_id: str,
        novo_status: str,
        alterado_por: str,
        motivo: str | None = None,
    ) -> dict:
        """
        Atualiza o status do pedido seguindo a máquina de estados.

        Transições válidas são definidas em StatusPedido.transicoes_validas().
        """
        pedido = self.repo_pedido.buscar_por_id(pedido_id)
        if not pedido:
            raise ResourceNotFoundError('Pedido')

        # Validar transição usando enum
    def atualizar_status(
        self,
        pedido_id: str,
        novo_status: str,
        alterado_por: str,
        motivo: str | None = None,
        restaurante_id: str | None = None,
    ) -> dict:
        pedido = self.repo_pedido.buscar_por_id(pedido_id)
        if not pedido:
            raise ResourceNotFoundError('Pedido')

        # Se for um pedido multi-restaurante
        if pedido.sub_pedidos:
            if restaurante_id:
                # Atualização feita pelo dono do restaurante para sua parte do pedido
                sub = next((sp for sp in pedido.sub_pedidos if str(sp.restaurante_id) == restaurante_id), None)
                if not sub:
                    raise ResourceNotFoundError('Sub-pedido do restaurante')
                
                # Validar transição usando a máquina de estados
                atual = StatusPedido(sub.status)
                if not atual.pode_transitar_para(novo_status):
                    raise InvalidStatusTransition(sub.status, novo_status)
                
                sub.status = novo_status
                sub.historico_status.append(MudancaStatus(
                    status=novo_status,
                    alterado_em=datetime.now(timezone.utc),
                    alterado_por=ObjectId(alterado_por),
                ))
            else:
                # Atualização (ex: cancelamento) feita pelo cliente para o pedido inteiro
                for sub in pedido.sub_pedidos:
                    atual = StatusPedido(sub.status)
                    if atual.pode_transitar_para(novo_status):
                        sub.status = novo_status
                        sub.historico_status.append(MudancaStatus(
                            status=novo_status,
                            alterado_em=datetime.now(timezone.utc),
                            alterado_por=ObjectId(alterado_por),
                        ))
            
            # Atualizar o status principal do Pedido baseado no estado combinado dos sub-pedidos
            statuses = [sp.status for sp in pedido.sub_pedidos]
            if all(s == StatusPedido.CANCELADO for s in statuses):
                pedido.status = StatusPedido.CANCELADO
            elif all(s == StatusPedido.ENTREGUE for s in statuses):
                pedido.status = StatusPedido.ENTREGUE
            elif any(s == StatusPedido.PREPARANDO for s in statuses):
                pedido.status = StatusPedido.PREPARANDO
            elif any(s == StatusPedido.PRONTO for s in statuses):
                pedido.status = StatusPedido.PRONTO
            elif any(s == StatusPedido.CONFIRMADO for s in statuses):
                pedido.status = StatusPedido.CONFIRMADO
            else:
                pedido.status = statuses[0]
                
            pedido.historico_status.append(MudancaStatus(
                status=pedido.status,
                alterado_em=datetime.now(timezone.utc),
                alterado_por=ObjectId(alterado_por),
            ))
            
            if novo_status == StatusPedido.CANCELADO and motivo:
                pedido.observacoes = f"{pedido.observacoes}\n[CANCELAMENTO]: {sanitize_input(motivo)}".strip()
                
            self.repo_pedido.salvar(pedido)
            
            logger.info("Pedido multi %s status atualizado para %s", pedido.numero_pedido, pedido.status)
            self._notificar_cliente(str(pedido.id), pedido.to_dict())
            
            pedido_dict = pedido.to_dict()
            if restaurante_id:
                self._filtrar_pedido_para_restaurante(pedido_dict, restaurante_id)
            return pedido_dict
        else:
            # Pedido de restaurante único (legado)
            atual = StatusPedido(pedido.status)
            if not atual.pode_transitar_para(novo_status):
                raise InvalidStatusTransition(pedido.status, novo_status)

            pedido.status = novo_status
            pedido.historico_status.append(MudancaStatus(
                status=novo_status,
                alterado_em=datetime.now(timezone.utc),
                alterado_por=ObjectId(alterado_por),
            ))

            if novo_status == StatusPedido.CANCELADO and motivo:
                pedido.observacoes = f"{pedido.observacoes}\n[CANCELAMENTO]: {sanitize_input(motivo)}".strip()

            self.repo_pedido.salvar(pedido)

            logger.info("Pedido %s status: %s → %s (por %s)", pedido.numero_pedido, atual, novo_status, alterado_por)
            self._notificar_cliente(str(pedido.id), pedido.to_dict())

            return pedido.to_dict()

    def buscar_pedido(self, pedido_id: str) -> dict | None:
        """Busca um pedido por ID."""
        pedido = self.repo_pedido.buscar_por_id(pedido_id)
        if not pedido:
            return None
        pedido_dict = pedido.to_dict()
        if pedido_dict.get('sub_pedidos'):
            nomes = []
            for sp in pedido_dict['sub_pedidos']:
                restaurante = self.repo_restaurante.find_by_id(sp['restaurante_id'])
                if restaurante:
                    nomes.append(restaurante.nome)
            pedido_dict['restaurante_nome'] = " + ".join(nomes) if nomes else "Multi-Restaurante"
        else:
            restaurante = self.repo_restaurante.find_by_id(str(pedido.restaurante_id))
            pedido_dict['restaurante_nome'] = restaurante.nome if restaurante else 'Restaurante'
        return pedido_dict

    def buscar_pedido_por_numero(self, numero_pedido: str) -> dict | None:
        """Busca um pedido pelo seu número legível."""
        pedido = self.repo_pedido.buscar_por_numero_pedido(numero_pedido)
        if not pedido:
            return None
        pedido_dict = pedido.to_dict()
        if pedido_dict.get('sub_pedidos'):
            nomes = []
            for sp in pedido_dict['sub_pedidos']:
                restaurante = self.repo_restaurante.find_by_id(sp['restaurante_id'])
                if restaurante:
                    nomes.append(restaurante.nome)
            pedido_dict['restaurante_nome'] = " + ".join(nomes) if nomes else "Multi-Restaurante"
        else:
            restaurante = self.repo_restaurante.find_by_id(str(pedido.restaurante_id))
            pedido_dict['restaurante_nome'] = restaurante.nome if restaurante else 'Restaurante'
        return pedido_dict

    def listar_pedidos_cliente(self, cliente_id: str, pagina: int = 1, tamanho_pagina: int = 10) -> dict:
        """Lista pedidos de um cliente."""
        resultado = self.repo_pedido.buscar_por_cliente(cliente_id, pagina=pagina, tamanho_pagina=tamanho_pagina)
        pedidos_dict = resultado.to_dict()
        
        # Obter IDs únicos de restaurantes e buscar seus nomes
        restaurantes_ids = set()
        for p in pedidos_dict['results']:
            if p.get('sub_pedidos'):
                for sp in p['sub_pedidos']:
                    restaurantes_ids.add(sp['restaurante_id'])
            elif p.get('restaurante_id'):
                restaurantes_ids.add(p['restaurante_id'])
                
        mapa_restaurantes = {}
        for rid in restaurantes_ids:
            restaurante = self.repo_restaurante.find_by_id(rid)
            if restaurante:
                mapa_restaurantes[rid] = restaurante.nome
                
        for p in pedidos_dict['results']:
            if p.get('sub_pedidos'):
                nomes = []
                for sp in p['sub_pedidos']:
                    nome = mapa_restaurantes.get(sp['restaurante_id'])
                    if nome:
                        nomes.append(nome)
                p['restaurante_nome'] = " + ".join(nomes) if nomes else "Multi-Restaurante"
            else:
                p['restaurante_nome'] = mapa_restaurantes.get(p['restaurante_id'], 'Restaurante')
            
        return pedidos_dict

    def listar_pedidos_restaurante(
        self,
        restaurante_id: str,
        filtro_status: str | None = None,
        pagina: int = 1,
        tamanho_pagina: int = 20,
    ) -> dict:
        """Lista pedidos de um restaurante."""
        resultado = self.repo_pedido.buscar_por_restaurante(
            restaurante_id, filtro_status=filtro_status, pagina=pagina, tamanho_pagina=tamanho_pagina,
        )
        pedidos_dict = resultado.to_dict()
        for p in pedidos_dict['results']:
            self._filtrar_pedido_para_restaurante(p, restaurante_id)
        return pedidos_dict

    def _filtrar_pedido_para_restaurante(self, pedido_dict: dict, restaurante_id: str) -> None:
        """Filtra os dados de um pedido multi-restaurante para conter apenas as informações de um restaurante específico."""
        if 'sub_pedidos' in pedido_dict and pedido_dict['sub_pedidos']:
            sub_pedido = next(
                (sp for sp in pedido_dict['sub_pedidos'] if sp['restaurante_id'] == restaurante_id),
                None
            )
            if sub_pedido:
                pedido_dict['itens'] = sub_pedido['itens']
                pedido_dict['total'] = sub_pedido['total']
                pedido_dict['taxa_entrega'] = sub_pedido['taxa_entrega']
                pedido_dict['valor_desconto'] = sub_pedido['valor_desconto']
                pedido_dict['codigo_cupom'] = sub_pedido['codigo_cupom']
                pedido_dict['status'] = sub_pedido['status']
                pedido_dict['historico_status'] = sub_pedido['historico_status']
                pedido_dict['restaurante_id'] = sub_pedido['restaurante_id']

    def validar_cupom(self, restaurante_id: str, codigo: str, total_carrinho: float) -> dict:
        """Valida um código de cupom e calcula desconto (usa ValidadorCupom — DRY)."""
        restaurante = self.repo_restaurante.find_by_id(restaurante_id)
        if not restaurante:
            raise ResourceNotFoundError('Restaurante')

        valor_desconto, codigo_validado = CouponValidator.validate_and_calculate(
            coupon_code=codigo,
            coupons=restaurante.cupons,
            cart_total=Decimal(str(total_carrinho)),
        )

        cupom = next((c for c in restaurante.cupons if c.codigo == codigo_validado), None)

        return {
            'valido': True,
            'codigo': codigo_validado,
            'valor_desconto': float(valor_desconto),
            'tipo_desconto': cupom.tipo_desconto if cupom else '',
            'descricao': cupom.descricao if cupom else '',
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Notificações WebSocket
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _notificar_restaurante(self, restaurante_id: str, dados_pedido: dict) -> None:
        """Envia notificação de novo pedido ao restaurante via WebSocket."""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'restaurant_{restaurante_id}',
                {'type': 'order.new', 'data': dados_pedido},
            )
        except Exception as e:
            logger.debug("Notificação WebSocket falhou (best-effort): %s", e)

    def _notificar_cliente(self, pedido_id: str, dados_pedido: dict) -> None:
        """Envia atualização de status ao cliente via WebSocket."""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'order_{pedido_id}',
                {'type': 'order.status_update', 'data': dados_pedido},
            )
        except Exception as e:
            logger.debug("Notificação WebSocket falhou (best-effort): %s", e)