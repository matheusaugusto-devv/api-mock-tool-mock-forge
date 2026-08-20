# specs/11_workspace_edit_and_delete.md

# feature: workspace_edit_and_delete

Permitir a edição do slug e a exclusão definitiva de workspaces (projetos) a partir do API Hub e via API JSON, mantendo o isolamento de dados e a integridade referencial.

## objetivo

Adicionar as operações de edição (renomeação do slug) e exclusão definitiva de projetos existentes, tanto pela interface do API Hub (HTMX) quanto pela API JSON, com confirmação obrigatória para a exclusão e garantia de cleanup em cascade de todos os dados associados (recursos, registros, configurações de autenticação e ApiKeys).

## contexto

Atualmente, a aplicação permite apenas criar e listar projetos. Não existe endpoint nem ação de UI para editar o slug de um projeto ou removê-lo. Os workspaces acumulam-se sem possibilidade de exclusão, e qualquer correção de slug exige manipulação direta do banco. O schema SQLite já possui `ON DELETE CASCADE` em todas as tabelas dependentes de `projects` (`resources`, `rows`, `project_auth`, `api_keys`), de modo que a exclusão do projeto limpa automaticamente todos os dados associados no nível do banco. Resta expor essa capacidade com UX seguro e API consistente.

## regras de negócio

- A edição de um projeto altera apenas o seu `slug`, mantendo o mesmo `id` e preservando todos os dados associados (recursos, registros, autenticação).
- O novo `slug` deve ser único, em minúsculas e no formato kebab-case (ex: `my-project`). A validação reutiliza as mesmas regras de criação de projeto (`validate_slug`).
- Não é permitido renomear um projeto para um slug já existente (conflito retorna erro de validação).
- A exclusão de um projeto é definitiva e remove em cascade: todos os recursos, registros, configurações de autenticação e ApiKeys vinculados.
- A exclusão exige confirmação explícita do usuário na interface (dialog/modal de confirmação com nome/slug do projeto).
- Após a exclusão na interface, o usuário retorna ao API Hub com a lista atualizada e sem o projeto removido.
- A edição e a exclusão devem respeitar as configurações de autenticação do próprio projeto alvo: se o projeto possuir método de autenticação ativo (`api_key`, `basic` ou `bearer`), as rotas da API JSON que realizam edição/exclusão devem exigir credenciais válidas e escopo `admin`. Projetos com autenticação `none` permanecem abertos a essas operações.
- Operações de edição e exclusão via API JSON sobre um projeto inexistente retornam `404 Not Found`.

## requisitos funcionais

### Backend (persistência)

- Adicionar método `Database.update_project(project_id: int, new_slug: str) -> dict | None` que atualiza o slug de um projeto pelo `id`, reaproveitando a `UNIQUE` constraint do SQLite para detectar duplicidade e retornando `None` quando o projeto não existir.
- Adicionar método `Database.delete_project(project_id: int) -> bool` que remove o projeto pelo `id` (a limpeza das tabelas dependentes ocorre via `ON DELETE CASCADE`), retornando `False` quando o projeto não existir.

### API JSON (REST)

- `PUT /api/projects/{slug}` para renomear o projeto: recebe `{"slug": "<novo-slug>"}`, valida com `validate_slug`, rejeita duplicidade com `409 Conflict`, retorna o projeto atualizado. Requer escopo `admin` quando a autenticação estiver ativa no projeto.
- `DELETE /api/projects/{slug}` para excluir o projeto: retorna `204 No Content` em caso de sucesso e `404` se o projeto não existir. Requer escopo `admin` quando a autenticação estiver ativa no projeto.

### Web (HTMX/UI)

- `POST /projects/{slug}/edit` recebendo `slug` (novo valor) no formulário e retornando a lista de projetos atualizada (`fragments/projects_list.html`) para requisições HTMX. Em caso de erro de validação, retorna status `422` com mensagem de erro exibida inline no card do projeto editado.
- `POST /projects/{slug}/delete` (ou `DELETE`) removendo o projeto e retornando a lista atualizada para requisições HTMX. Retorna `404` caso o projeto não exista.
- Atualizar `fragments/projects_list.html` para incluir, em cada card de projeto:
  - Botão de edição do slug (`hx-get` abre um formulário inline ou `hx-post` direto com campo editável).
  - Botão de exclusão com confirmação obrigatória (através de `hx-confirm` com prompt contendo o slug do projeto, ou modal nativo do HTMX).
- Atualizar `projects.html`/`projects_list.html` para refletir imediatamente a lista após edição ou exclusão sem reload completo da página.

## requisitos não funcionais

- Reutilizar a validação existente (`validate_slug`) e as constraints do SQLite para detectar duplicidade — sem lógica customizada de checagem de unicidade.
- Manter as ações de edição e exclusão via HTMX sem recarregar a página inteira (atualização apenas do `#projects-list-container`).
- Feedback visual imediato de erro (slug inválido/duplicado) e de sucesso (remoção do card/item atualizado).
- Cobertura de testes unitários igual ou superior a 90% para os novos fluxos.

## critérios de aceitação

- API JSON: `PUT /api/projects/{slug}` com slug válido e inédito retorna o projeto com o novo slug e status `200`.
- API JSON: `PUT /api/projects/{slug}` com slug duplicado retorna status `409 Conflict`.
- API JSON: `PUT /api/projects/{slug}` com slug inválido (não kebab-case) retorna status `400`.
- API JSON: `PUT /api/projects/{slug}` sobre projeto inexistente retorna `404`.
- API JSON: `DELETE /api/projects/{slug}` remove o projeto e retorna `204 No Content`.
- API JSON: `DELETE /api/projects/{slug}` sobre projeto inexistente retorna `404`.
- API JSON: quando o projeto alvo possuir autenticação ativa (ex.: `api_key`), `PUT`/`DELETE` sem credenciais válidas e escopo `admin` retornam `401`/`403` conforme o caso. Projeto com autenticação `none` permite as operações livremente.
- API JSON: `DELETE /api/projects/{slug}` remove em cascade os recursos, registros, configurações de autenticação e ApiKeys vinculados ao projeto excluído (verificado consultando as tabelas dependentes após a exclusão).
- API JSON: `PUT /api/projects/{slug}` preserva o `id` do projeto e todos os dados associados (recursos e registros continuam acessíveis sob o novo slug).
- UI/HTMX: ao editar o slug de um projeto no API Hub, o card é atualizado in-place com o novo slug sem recarregar a página.
- UI/HTMX: ao tentar editar para um slug inválido ou duplicado, o erro é exibido inline no card sem alterar o projeto.
- UI/HTMX: ao clicar em excluir um projeto, uma confirmação explícita é exigida (ex.: `hx-confirm` contendo o slug do projeto).
- UI/HTMX: após confirmar a exclusão, o card do projeto é removido da lista e os recursos/dados deixam de ser acessíveis via `/api/{slug}/...`.
- UI/HTMX: tentativa de excluir/editar um projeto inexistente via web retorna `404` (ou mensagem equivalente) sem remover outros itens.
- Testes automatizados cobrindo todos os critérios de aceitação acima com cobertura >= 90%.

## casos de erro

- Novo slug não está em kebab-case: `400 Bad Request` (API) ou mensagem inline de validação (UI).
- Novo slug já existe em outro projeto: `409 Conflict` (API) ou mensagem de erro inline no card (UI).
- Projeto alvo da edição/exclusão não existe: `404 Not Found`.
- Projeto com autenticação ativa e requisição sem credenciais: `401 Unauthorized`.
- Projeto com autenticação ativa e credenciais válidas mas sem escopo `admin`: `403 Forbidden`.
- Exclusão sem confirmação na UI: ação bloqueada pelo `hx-confirm` (não dispara requisição).

## fora de escopo

- Soft delete / lixeira / restauração de projetos excluídos.
- Edição de metadados do projeto além do `slug`.
- Transferência de recursos/dados entre projetos distintos.
- Histórico ou auditoria de quem executou a edição/exclusão.
- Renomeação automática de referências externas (exportações previamente baixadas, coleções Postman, etc.).
