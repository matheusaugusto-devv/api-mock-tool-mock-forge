# specs/09_auth_core_and_tokens.md

# feature: auth_core_and_tokens

Implementar a camada de segurança, gerenciamento de autenticação por projeto (ApiKey, Basic Auth e Bearer Token com expiração de 5 minutos), geração de tokens e proteção das rotas da API.

## objetivo
Permitir que projetos configurem métodos de autenticação e garantam que apenas requisições autenticadas e autorizadas acessem suas rotas e recursos.

## contexto
Atualmente, as rotas `/api/{project_slug}/...` são públicas. Para simular cenários reais de desenvolvimento de APIs, cada projeto precisa suportar autenticação configurável com controle de acesso baseado em escopos para ApiKeys e emissão de Bearer Tokens com validade controlada.

## regras de negócio
- Cada projeto pode configurar um dos seguintes modos de autenticação: `none` (padrão/desativado), `api_key`, `basic` ou `bearer`.
- Todas as rotas sob `/api/{project_slug}/...` devem ser protegidas pelo método de autenticação ativo do projeto, exceto a rota `POST /api/{project_slug}/auth`.
- **ApiKey**:
  - Requisição deve fornecer a chave via header `X-API-Key` ou `Authorization: ApiKey <key>`.
  - ApiKeys possuem escopos vinculados: `read` (para requisições `GET`), `write` (para requisições `POST`, `PUT`, `DELETE`), `admin` (acesso irrestrito) e `auth` (permissão para gerar Bearer Tokens).
  - Requisições com chaves inválidas retornam status `401 Unauthorized`.
  - Requisições com chaves válidas mas sem escopo necessário retornam status `403 Forbidden`.
- **Basic Auth**:
  - Requisição deve fornecer o header `Authorization: Basic <base64(user:pass)>`.
  - Credenciais devem corresponder às configuradas no projeto.
  - Credenciais ausentes ou inválidas retornam status `401 Unauthorized` com header `WWW-Authenticate: Basic realm="Project API"`.
- **Bearer Token e Rota `/api/{project_slug}/auth`**:
  - Rota `POST /api/{project_slug}/auth` é pública (não exige cabeçalho de autenticação Bearer para ser acessada).
  - A geração do Bearer Token exige obrigatoriamente uma ApiKey válida fornecida no corpo da requisição (`{"apiKey": "<key>"}`) ou via header `X-API-Key` / `Authorization: ApiKey <key>`.
  - O backend valida se a ApiKey possui o escopo `auth` (ou `admin`).
    - Caso a ApiKey não seja informada ou seja inválida: retorna status `401 Unauthorized`.
    - Caso a ApiKey seja válida mas não possua o escopo `auth`: retorna status `403 Forbidden`.
    - Caso a ApiKey seja válida e possua o escopo `auth`: gera e emite um Bearer Token assinado com expiração de 5 minutos (300 segundos), herdando os escopos da chave, e retorna `{ "access_token": "<token>", "token_type": "bearer", "expires_in": 300 }`.
  - Quando o modo de autenticação do projeto estiver configurado como `bearer`, as rotas sob `/api/{project_slug}/...` (exceto `/auth`) exigem `Authorization: Bearer <token>` válido e não expirado.

## requisitos funcionais
- Tabela ou campos no banco SQLite para armazenar as configurações de autenticação do projeto (`auth_type`, `basic_username`, `basic_password`, `secret_key`).
- Tabela `api_keys` associada ao projeto com suporte a múltiplos escopos por chave.
- Rota `POST /api/{project_slug}/auth` para emissão do Bearer Token ou aviso de desativação.
- Middleware / interceptor de segurança validando credenciais, expiração e escopos em requisições `/api/{project_slug}/...`.
- CRUD/gerenciador de ApiKeys com geração de strings aleatórias seguras.

## requisitos não funcionais
- Utilizar bibliotecas padrão do Python (`hashlib`, `hmac`, `secrets`, `base64`, `time`) evitando dependências externas pesadas.
- Validação rápida de tokens sem sobrecarga de latência nas rotas dinâmicas.

## critérios de aceitação
- Projeto com modo `none` permite requisições sem credenciais.
- Projeto com modo `api_key` rejeita requisições sem chave (401) e com chave sem o escopo exigido (403).
- Projeto com modo `basic` valida usuário e senha configurados e rejeita credenciais incorretas (401).
- Rota `POST /api/{project_slug}/auth` retorna token com expiração de 5 minutos quando ApiKey válida possuir escopo `auth`.
- Rota `POST /api/{project_slug}/auth` retorna status 401 quando ApiKey não for informada ou for inválida.
- Rota `POST /api/{project_slug}/auth` retorna status 403 quando ApiKey não possuir escopo `auth`.
- Token expirado (após 5 minutos) é rejeitado com status 401.
- Cobertura de testes unitários superior a 90% para todos os fluxos de autenticação e validação de escopos.

## casos de erro
- ApiKey não informada ou inexistente: `401 Unauthorized`.
- ApiKey sem escopo apropriado para a operação: `403 Forbidden`.
- Bearer Token malformado ou com assinatura inválida: `401 Unauthorized`.
- Bearer Token expirado: `401 Unauthorized`.
- Payload inválido na rota de autenticação: `400 Bad Request`.

## fora de escopo
- Refresh tokens de longa duração.
- Provedores OAuth2 externos (Google, GitHub, etc).
- Gerenciamento de múltiplos usuários por projeto com controle RBAC complexo além das ApiKeys.
