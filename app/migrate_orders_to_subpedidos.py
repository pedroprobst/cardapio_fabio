import os
import django
import sys
from decimal import Decimal
from datetime import datetime, timezone

# Configurar Django para acessar models e configurações se necessário
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings.base')
django.setup()

import mongoengine as me
from django.conf import settings
from apps.orders.documents import Pedido, SubPedido
from apps.restaurants.documents import Restaurante
from bson import ObjectId

def run_migration():
    print("Iniciando migração de pedidos legados para sub_pedidos...")
    
    # Conectar ao MongoDB
    me.connect(
        db=settings.MONGODB_DATABASES['default']['name'],
        host=settings.MONGODB_DATABASES['default']['host'],
        uuidRepresentation='standard'
    )
    
    # Buscar pedidos que têm restaurante_id (formato legado) e não têm sub_pedidos
    # Usar query raw do PyMongo para performance e acesso direto aos campos
    collection = Pedido._get_collection()
    
    query = {
        'restaurante_id': {'$ne': None},
        '$or': [
            {'sub_pedidos': {'$exists': False}},
            {'sub_pedidos': {'$size': 0}}
        ]
    }
    
    total_pedidos = collection.count_documents(query)
    print(f"Encontrados {total_pedidos} pedidos para migrar.")
    
    if total_pedidos == 0:
        print("Nenhuma migração necessária.")
        return

    migrados = 0
    erros = 0
    
    # Processar em batches
    cursor = collection.find(query)
    for pedido_data in cursor:
        try:
            pedido_id = pedido_data['_id']
            rest_id = pedido_data.get('restaurante_id')
            itens = pedido_data.get('itens', [])
            
            if not rest_id or not itens:
                print(f"Pedido {pedido_id} ignorado (sem restaurante_id ou itens)")
                continue
                
            # Construir o dict do sub_pedido sem os campos de snapshot
            sub_pedido = {
                'restaurante_id': rest_id,
                'itens': itens,
                'total': pedido_data.get('total', 0),
                'taxa_entrega': pedido_data.get('taxa_entrega', 0),
                'valor_desconto': pedido_data.get('valor_desconto', 0),
                'codigo_cupom': pedido_data.get('codigo_cupom', ''),
                'status': pedido_data.get('status', 'pendente'),
                'historico_status': pedido_data.get('historico_status', [])
            }
            
            # Atualizar o documento via update_one para ser atômico
            # Removendo os campos antigos do nível raiz para limpar o banco
            result = collection.update_one(
                {'_id': pedido_id, 'sub_pedidos': {'$exists': False}},
                {
                    '$set': {'sub_pedidos': [sub_pedido]},
                    '$unset': {'restaurante_id': "", 'itens': ""}
                }
            )
            
            if result.modified_count == 0:
                # Tentar com $size: 0 se $exists: False falhar
                result = collection.update_one(
                    {'_id': pedido_id, 'sub_pedidos': {'$size': 0}},
                    {
                        '$push': {'sub_pedidos': sub_pedido},
                        '$unset': {'restaurante_id': "", 'itens': ""}
                    }
                )
                
            if result.modified_count > 0:
                migrados += 1
                if migrados % 100 == 0:
                    print(f"Migrados {migrados}/{total_pedidos}...")
            else:
                print(f"Pedido {pedido_id} não atualizado (talvez já migrado concorrentemente).")
                
        except Exception as e:
            erros += 1
            print(f"Erro ao migrar pedido {pedido_data.get('_id')}: {e}")

    print(f"\nMigração concluída!")
    print(f"Sucesso: {migrados}")
    print(f"Erros: {erros}")

if __name__ == "__main__":
    run_migration()
