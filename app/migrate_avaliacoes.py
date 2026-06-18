import os
import django
import sys

# Configurar Django para acessar models e configurações
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings.base')
django.setup()

import mongoengine as me
from django.conf import settings
from apps.restaurants.documents import Restaurante

def run_migration():
    print("Iniciando migração de avaliacoes para avaliacao.avaliacoes...")
    
    # Conexão com o MongoDB já é feita no django.setup()
    
    collection = Restaurante._get_collection()
    
    query = {
        'avaliacoes': {'$exists': True}
    }
    
    total_restaurantes = collection.count_documents(query)
    print(f"Encontrados {total_restaurantes} restaurantes para verificar/migrar.")
    
    if total_restaurantes == 0:
        print("Nenhuma migração necessária.")
        return

    migrados = 0
    erros = 0
    
    cursor = collection.find(query)
    for data in cursor:
        try:
            restaurante_id = data['_id']
            avaliacoes_legado = data.get('avaliacoes', [])
            
            # Move avaliacoes to avaliacao.avaliacoes and remove the old field
            result = collection.update_one(
                {'_id': restaurante_id},
                {
                    '$set': {'avaliacao.avaliacoes': avaliacoes_legado},
                    '$unset': {'avaliacoes': ""}
                }
            )
            
            if result.modified_count > 0:
                migrados += 1
                
        except Exception as e:
            erros += 1
            print(f"Erro ao migrar restaurante {data.get('_id')}: {e}")

    print(f"\nMigração concluída!")
    print(f"Sucesso: {migrados}")
    print(f"Erros: {erros}")

if __name__ == "__main__":
    run_migration()
