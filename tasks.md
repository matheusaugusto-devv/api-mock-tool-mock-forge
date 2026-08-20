# tasks.md

## Feature: gestao_de_projetos_e_engine_rest_dinamica (specs/01_core_engine.md)

- [x] Criar camada de persistência SQLite (projetos, recursos/schemas, dados)
- [x] Endpoint de criação e listagem de projetos (slug kebab-case único)
- [x] Endpoint de criação e listagem de recursos/schemas por projeto
- [x] Rotas dinâmicas `GET/POST` em `/api/{project_slug}/{resource}`
- [x] Rotas dinâmicas `GET/PUT/DELETE` em `/api/{project_slug}/{resource}/{row_id}`
- [x] Suporte a `_sort`, `_order`, `_page`, `_limit` e filtros por campo no GET
- [x] ExceptionHandler global para 404 (recursos não encontrados) e 400 (payload inválido)
- [x] Isolamento de dados entre projetos
- [x] Testes automatizados cobrindo os critérios de aceitação (28 testes)

## Feature: dashboard_htmx_e_workspace (specs/02_dashboard_ui.md)

- [x] Criar templates Jinja2 base e parciais/fragmentos para HTMX
- [x] Implementar API Hub (`/` e `/projects`) com listagem e busca
- [x] Implementar criação de projetos via formulário HTMX (`hx-post`) com redirecionamento para Workspace (`HX-Redirect` ou `HX-Location`)
- [x] Implementar Workspace (`/projects/{slug}`) com navegação por abas reativas (`hx-get` preservando URL / `hx-push-url`)
- [x] Implementar Schema Builder com formulário HTMX para criação dinâmica de recursos/colunas
- [x] Validações de regras de negócio: colunas duplicadas proibidas e nomes de recursos sanitizados
- [x] Testes unitários para renderização SSR e fragmentos HTMX com cobertura >= 90%

## Feature: gerador_de_mocks_faker_e_importacao (specs/03_mock_faker_import.md)

- [x] Mapeamento de tipos/geradores Faker com fallback para `faker.text()`
- [x] Geração automatizada de N registros sintéticos para um recurso
- [x] Parser de especificações OpenAPI 3.0 (criação automática de schemas e tabelas SQLite)
- [x] Exportação e importação de configuração do projeto (JSON e OpenAPI 3.0)
- [x] Data Explorer: visualização tabular reativa, busca rápida, paginação/filtragem
- [x] Ações inline de alteração e exclusão no Data Explorer via HTMX (`hx-post`, `hx-delete`)
- [x] Interface e botões para "Gerar Mocks", Importar e Exportar
- [x] Testes automatizados cobrindo todos os critérios de aceitação com cobertura >= 90%

## Feature: testador_de_endpoints_e_logs_sse (specs/04_testing_and_logs.md)

- [x] Middleware de auditoria para capturar e registrar chamadas em `/api/...` com timestamp, método, path, status e tempo (ms)
- [x] Publicador de eventos em tempo real (`LogEventManager`) e rota SSE `/events/logs/{project_slug}` filtrando por projeto
- [x] Endpoint Tester na UI do Workspace (`tab=tester`) com formulário para método, path, corpo JSON e visualização da resposta
- [x] Painel de logs em tempo real na UI (`tab=logs`) usando extensão SSE do HTMX (`hx-ext="sse"`)
- [x] Endpoint `/projects/{slug}/test-request` executando chamadas contra as rotas da aplicação via cliente assíncrono
- [x] Testes unitários e de integração cobrindo todos os critérios de aceitação com cobertura >= 90%

## Feature: cli_empacotamento_e_distribuicao (specs/05_cli_and_distribution.md)

- [x] Implementar CLI com Typer (`mock-forge start`) aceitando `--port`, `--host`, `--db-path`
- [x] Abertura automática do navegador no dashboard ao iniciar e encerramento gracioso (SIGINT / fechamento SQLite)
- [x] Configurar `pyproject.toml` para execução via `pipx run mock-forge` e entrypoint CLI
- [x] Configurar script/especificação de build do PyInstaller para executáveis únicos
- [x] Criar `README.md` com guia rápido de instalação e exemplos de integração com frontends
- [x] Criar testes unitários para a CLI e garantir cobertura total da suite >= 90%

## Feature: add_json_file_support (specs/06_add_json_file_support.md)

- [x] Suporte à importação de arquivo JSON com dados para popular resource no Data Explorer
- [x] Parsing de formato JSON (lista de objetos ou objeto único) para inserção no SQLite
- [x] Feedback visual de erro/sucesso em caso de falhas de parsing ou sintaxe inválida
- [x] Testes automatizados unitários e de integração com cobertura total >= 90%

## Feature: add_endpoints_tab (specs/07_add_endpoints_tab.md)

- [x] Adicionar aba Endpoints na interface do Workspace
- [x] Botão "+ Add Endpoint" com formulário para criação dinâmica de endpoints/recursos
- [x] Tabela de listagem dos endpoints existentes exibindo schema e rotas
- [x] Ações inline de edição e exclusão de endpoints na tabela
- [x] Endpoints na API REST para operações CRUD de endpoints/resources
- [x] Testes unitários e de integração cobrindo a aba de endpoints com cobertura >= 90%

## Feature: desktop_responsive_layout (specs/08_desktop_responsive_layout.md)

- [x] Ajustar estilos base (`base.html`) com container fluido e regras de responsividade para desktop
- [x] Garantir comportamento responsivo com flex-wrap em formulários e fragmentos de templates
- [x] Garantir visualização com scroll horizontal adequado nas tabelas de Endpoints, Data Explorer e Logs
- [x] Criar/atualizar testes automatizados para validar layout e elementos responsivos

## Feature: auth_core_and_tokens (specs/09_auth_core_and_tokens.md)

- [x] Implementar tabelas de configuração de autenticação e ApiKeys no SQLite (`src/db/database.py`)
- [x] Implementar utilitários de geração/validação de ApiKey e Bearer Tokens com HMAC/expiração de 5 min (`src/core/auth.py`)
- [x] Implementar rota automática `POST /api/{project_slug}/auth` (emissão de token Bearer ou aviso de desativação)
- [x] Implementar middleware/validação de autenticação e verificação de escopos para rotas `/api/{project_slug}/...`
- [x] Criar testes unitários e de integração cobrindo todos os critérios de aceitação e cobertura >= 90%

## Feature: auth_ui_tab (specs/10_auth_ui_tab.md)

- [x] Adicionar aba "Authentication" no menu do Workspace (`src/templates/workspace.html`)
- [x] Criar fragmento de template `src/templates/fragments/tab_auth.html` (método de autenticação, basic auth inputs, painel bearer e gerenciador de ApiKeys com escopos)
- [x] Implementar endpoints web em `src/router/web.py` para salvar configurações, criar ApiKeys e revogar ApiKeys via HTMX
- [x] Criar testes automatizados em `tests/test_auth_ui.py` cobrindo todos os critérios de aceitação com cobertura >= 90%

## Feature: workspace_edit_and_delete (specs/11_workspace_edit_and_delete.md)

- [x] Implementar `Database.update_project(project_id, new_slug)` e `Database.delete_project(project_id)` em `src/db/database.py`
- [x] Implementar `PUT /api/projects/{slug}` para renomear projeto com validação, 409 em duplicidade e exigência de escopo `admin` quando auth ativa
- [x] Implementar `DELETE /api/projects/{slug}` com remoção em cascade (via FK) e exigência de escopo `admin` quando auth ativa
- [x] Implementar rotas web `POST /projects/{slug}/edit` e `POST /projects/{slug}/delete` retornando a lista HTMX atualizada
- [x] Atualizar `fragments/projects_list.html` com botões de editar e excluir (com `hx-confirm`) por card
- [x] Criar testes automatizados em `tests/test_workspace_edit_and_delete.py` cobrindo todos os critérios de aceitação com cobertura >= 90%




