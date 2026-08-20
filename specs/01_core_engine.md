# specs/01_core_engine.md

# feature: gestao_de_projetos_e_engine_rest_dinamica

Criar a engine base em FastAPI com SQLite para suportar múltiplos projetos isolados e roteamento dinâmico de endpoints sob o prefixo `/api/{project_slug}/{resource}`.

## requisitos
- Criar a camada de persistência para armazenar os projetos e seus respectivos schemas e dados.
- Mapear rotas dinâmicas HTTP (GET, POST, PUT, DELETE) com base no `project_slug` e `resource`.
- Implementar suporte a ordenação (`?_sort=coluna`), paginação (`?_page=1&_limit=10`) e filtros por campo em requisições GET.
- Criar um `ExceptionHandler` global para tratar recursos não encontrados (404) e erros de sintaxe em payloads (400).

## regras de negócio
- O `project_slug` deve ser único, em minúsculas e separado por hífens (kebab-case).
- Os dados de um projeto não podem ser acessados ou sobrescritos por requisições pertencentes a outro projeto.

## critérios de aceitação
- Testes unitários para validação do roteador dinâmico (`GET`, `POST`, `PUT`, `DELETE`).
- Testes de isolamento garantindo que `/api/proj-a/users` não retorne dados de `/api/proj-b/users`.
- Testes de integração para os parâmetros de query (paginação, ordenação e filtros).