# 5. Arquitetura do Sistema

Este documento descreve as decisões de stack tecnológica e a organização estrutural de diretórios do projeto Cardápio Online.

---

## Sumário

- [5.1 Stack Tecnológico Base](#51-stack-tecnológico-base)
- [5.2 Estrutura de Diretórios](#52-estrutura-de-diretórios)
- [5.3 Descrição dos Diretórios](#53-descrição-dos-diretórios)

---

## 5.1 Stack Tecnológico Base

O projeto utiliza uma arquitetura baseada em **Django** integrado a um banco de dados NoSQL **MongoDB** através do ODM **MongoEngine**.

- **Django (5.0+)**: Framework web principal para controle de rotas, segurança e gerenciamento do sistema.
- **MongoDB (7.x)**: Banco de dados NoSQL baseado em documentos, oferecendo flexibilidade e alta performance de leitura.
- **MongoEngine**: ODM (*Object-Document Mapper*) utilizado para mapear coleções do MongoDB diretamente em objetos Python, facilitando a manipulação dos dados no Django.

---

## 5.2 Estrutura de Diretórios

A organização do projeto foi dividida em módulos para facilitar a manutenção e o desenvolvimento do sistema.

```text
cardapio-online/
├── app/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── authentication/      # Cadastro e login
│   ├── restaurants/         # Restaurantes, produtos e cupons
│   ├── orders/              # Pedidos
│   └── core/                # Configurações e utilidades comuns
│
├── templates/               # Páginas HTML
├── static/                  # CSS, JavaScript e imagens
├── media/                   # Uploads do sistema
├── docs/                    # Documentação do projeto
├── requirements.txt         # Dependências do projeto
└── manage.py                # Inicialização do Django
```

## 5.3 Descrição dos Diretórios

| Diretório          | Finalidade                                                |
| ------------------ | --------------------------------------------------------- |
| `app`              | Configurações principais do Django.                       |
| `authentication`   | Funcionalidades de cadastro e login dos usuários.         |
| `restaurants`      | Gerenciamento de restaurantes, produtos e cupons.         |
| `orders`           | Registro e acompanhamento dos pedidos.                    |
| `core`             | Componentes compartilhados entre os módulos.              |
| `templates`        | Arquivos HTML utilizados pelo sistema.                    |
| `static`           | Arquivos estáticos, como CSS e JavaScript.                |
| `media`            | Imagens enviadas pelos usuários e restaurantes.           |
| `docs`             | Documentação do projeto.                                  |
| `requirements.txt` | Lista das bibliotecas utilizadas.                         |
| `manage.py`        | Arquivo responsável pela execução dos comandos do Django. |
