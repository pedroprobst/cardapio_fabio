# 7. Modelagem Dinâmica: Diagramas de Sequência

Este documento ilustra a dinâmica comportamental do sistema, expondo a comunicação entre camadas através de fluxos operacionais mapeados no tempo.

---

## Sumário

- [7.1 Fluxo Completo de Transação Comercial (Pedido)](#71-fluxo-completo-de-transação-comercial-pedido)
- [7.2 Fluxo Arquitetural de Provisionamento e *Upload*](#72-fluxo-arquitetural-de-provisionamento-e-upload)
- [7.3 Orquestração de Identidade Distribuída (OAuth 2.0)](#73-orquestração-de-identidade-distribuída-oauth-20)
- [7.4 Máquina de Estados (State Machine) Logística](#74-máquina-de-estados-state-machine-logística)

---

## 7.1 Fluxo Completo de Transação Comercial (Pedido)

O diagrama de sequência a seguir mapeia a interação desde o consumo passivo do cardápio pelo cliente, passando pela criação da cesta virtual, até o comissionamento do pedido para o terminal em tempo real do restaurante.

```mermaid
sequenceDiagram
    participant C as Cliente Final
    participant UI as Client Application (UI)
    participant API as Gateway Layer
    participant Core as Order Services
    participant DB as NoSQL Store
    participant WS as Channel Layer (WebSocket)

    %% Estágio de Descoberta
    note right of C: ETAPA 1: NAVEGAÇÃO E CARRINHO
    C->>UI: Navega na página do Cardápio
    UI->>API: GET /restaurants/:id/products
    API->>Core: list_products_by_tenant(id)
    Core->>DB: find({ "slug": id })
    DB-->>Core: Documento de Restaurante (Embedding)
    Core-->>API: Coleção Serializada de Produtos
    API-->>UI: HTTP 200 (Payload JSON)
    C->>UI: Ação: "Adicionar ao Carrinho"
    UI->>UI: Persiste Cesta em localStorage

    %% Estágio de Transação
    note right of C: ETAPA 2: CHECKOUT E ORQUESTRAÇÃO
    C->>UI: Dispara Ação: "Finalizar Pedido"
    UI->>API: POST /orders/ (Items, Metadata) + Auth Header
    API->>Core: create_order(payload, customer_id)
    
    %% Validação de Integridade
    Core->>Core: Validate Constraints (Tenant Ativo, Produtos Disponíveis)
    Core->>Core: Desmembra itens em N Sub-Pedidos por Restaurante
    Core->>Core: Executa Snapshot Financeiro (BSON) para cada sub-pedido
    
    Core->>DB: insertOne(Order Document containing sub_pedidos)
    DB-->>Core: Order Object ID gerado
    Core-->>API: Representação de Domínio (Order com sub_pedidos)
    
    %% Comunicação Assíncrona (Event-driven)
    API-)WS: Broadcast Assíncrono (notify_new_order iterado por sub-pedido)
    WS-)UI: Sincroniza Múltiplos Terminais de Gestores (Tenant_WS_Groups 1..N)
    
    API-->>UI: HTTP 201 Created (Recibo Transacional: #ORD-XXXX)
    UI-->>C: Confirmação Visual Renderizada com divisão por Restaurante
```

---

## 7.2 Fluxo Arquitetural de Provisionamento e *Upload*

O fluxo administrativo descreve a sequência exigida para a criação do ambiente virtual de um locatário, lidando explicitamente com a complexidade transacional de anexos e armazenamento local.

```mermaid
sequenceDiagram
    participant G as Gestor Proprietário
    participant UI as Backoffice (Dashboard)
    participant API as API de Serviços
    participant BL as Tenant Business Logic
    participant DB as MongoDB Atlas
    participant Storage as Armazenamento Local

    G->>UI: Submete Formulário "Novo Restaurante" (inclui binário de imagem)
    UI->>API: POST /restaurants/ (Multipart Form-Data)
    API->>BL: handle_restaurant_creation()
    
    %% Fase de Armazenamento
    BL->>BL: Avalia Sanitização e Validadores MIME Type
    BL->>Storage: Salva Arquivo Binário da Capa
    Storage-->>BL: HTTP 200 OK + URL Absoluta Local
    
    %% Fase de Registro e Finalização
    BL->>DB: insertOne(Tenant Payload contendo URL)
    DB-->>BL: Success Object Confirmation
    BL-->>API: Rest Object Payload
    API-->>UI: HTTP 201 Created
    UI-->>G: Apresentação da View de Gestão Ativa
```

---

## 7.3 Orquestração de Identidade Distribuída (OAuth 2.0)

A delegação da confiabilidade de acesso utiliza as diretrizes do protocolo *Authorization Code Flow* integrado aos microsserviços do Google Accounts.

```mermaid
sequenceDiagram
    participant U as Entidade de Usuário
    participant SPA as Single Page Application
    participant SYS as Auth API Layer
    participant Srv as Session Management
    participant IdP as Google Identity Provider (IdP)

    U->>SPA: Invoca SSO ("Continuar com Google")
    SPA->>IdP: Redirect Authorization Code Request
    IdP-->>U: Página de Consentimento do Google
    U->>IdP: Aprova Permissão Perfil Básico (Scope)
    IdP-->>SPA: Redirect URi contendo 'Auth Code' Temporal
    
    %% Troca Segura de Credenciais (Back-channel)
    SPA->>SYS: POST /api/auth/google/ { code: XYZ }
    SYS->>Srv: Process OAuth Callback
    Srv->>IdP: POST /token (Client Secret Exchange)
    IdP-->>Srv: IdP Access Token + JWT Identity Token
    
    %% Processamento Interno e Transição
    Srv->>Srv: Decode Metadata & find_or_create_user(email)
    Srv->>Srv: Emissão RS256 Plataforma JWT (Access + Refresh)
    Srv-->>SYS: Emissão de Sessão Local (Internal Tokens)
    SYS-->>SPA: HTTP 200 OK
    SPA->>U: Desbloqueia Visualização do Dashboard Autenticado
```

---

## 7.4 Máquina de Estados (State Machine) Logística

A evolução sequencial de um pedido reflete processos estritamente lineares. No novo modelo arquitetural, a Máquina de Estados atua independentemente em cada **Sub-Pedido** (nível de restaurante). Retrocessos de transição não são suportados nativamente (exceto mediante falhas forçadas - cancelamento). O diagrama a seguir representa as fronteiras dessa transição de estado por sub-pedido.

```mermaid
stateDiagram-v2
    %% Diretrizes da Maquina
    direction LR
    
    %% Estados Base
    [*] --> PENDING: Inserção Automática
    
    PENDING --> CONFIRMED: Operador Valida Requisição
    CONFIRMED --> PREPARING: Encaminhamento à Cozinha
    PREPARING --> READY: Etiquetagem para Logística
    READY --> DELIVERED: Entregue (Encerramento Contábil)
    
    DELIVERED --> [*]
    
    %% Tratamento de Exceção
    PENDING --> CANCELLED: Recusa Operacional/Estoque
    CONFIRMED --> CANCELLED: Estorno Forçado
    
    CANCELLED --> [*]: Falha Terminal
    
    %% Notas Operacionais
    note right of PENDING
      Sistema envia pulso WebSocket 
      para o Painel do Gestor.
    end note
    
    note left of READY
      Cliente recebe pulso de alerta
      na aplicação cliente.
    end note
```

### Regras de Transição de Contrato
| Mutação de Estado | Ator Executor | Efeito Colateral na Arquitetura |
| --- | --- | --- |
| `[INIT]` → `pending` | API Node | Pedido é registrado no DB, submetendo o pulso inicial ao nó MQTT/WebSocket do Tenant. |
| `pending` → `confirmed` | Gestor (Owner) | Validação afirmativa enviada via WS para a interface do cliente de forma assíncrona. |
| `confirmed` → `preparing` | Gestor (Owner) | Atualização visual transmitida à SPA (Single Page Application) do cliente. |
| `preparing` → `ready` | Gestor (Owner) | Liberação para coleta; Alerta emitido para o Cliente de *pickup* iminente. |
| `ready` → `delivered` | Gestor (Owner) | *Soft-lock* (Congelamento) do pedido, transição para o Histórico Arquivado no DB. |
| `[QUALQUER]` → `cancelled` | Híbrido | Modificador Excepcional. Exige preenchimento de justificativa obrigatória e anula garantias financeiras. |
