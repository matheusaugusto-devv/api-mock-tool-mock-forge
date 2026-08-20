# specs/10_auth_ui_tab.md

# feature: auth_ui_tab

Adicionar a aba "Authentication" no Workspace do projeto para configuração do método de autenticação, criação e revogação de ApiKeys com vinculação de escopos e visualização de instruções de uso.

## objetivo
Fornecer uma interface intuitiva dentro do Dashboard para que os usuários possam habilitar métodos de autenticação na API do projeto, gerar ApiKeys atribuindo escopos e visualizar instruções de como usar e testar o Bearer Token.

## contexto
Com o motor de segurança implementado, os desenvolvedores precisam configurar visualmente a autenticação de seus projetos sem necessidade de editar manualmente arquivos de configuração ou bancos de dados.

## regras de negócio
- A aba "Authentication" deve estar acessível na navegação de abas do Workspace (`/projects/{slug}?tab=auth`).
- O usuário pode selecionar o método de autenticação da API:
  - `None` (Desativado)
  - `ApiKey`
  - `Basic Auth`
  - `Bearer Token`
- **Seção de Configuração do Método**:
  - Salva as alterações via HTMX sem recarregar a página inteira.
  - Para `Basic Auth`: Exibe campos para editar Username e Password.
  - Para `Bearer Token`: Exibe painel explicativo sobre como gerar o token chamando `POST /api/{slug}/auth` usando uma ApiKey com escopo `auth`, indicando o tempo de expiração de 5 minutos e exemplos de cabeçalho `Authorization: Bearer <token>`.
- **Seção de Gerenciamento de ApiKeys e Escopos**:
  - Formulário para gerar nova ApiKey com:
    - Campo de nome/descrição da chave.
    - Checkboxes de seleção de escopos: `read` (Leitura), `write` (Escrita), `auth` (Geração de Token Bearer) e `admin` (Acesso Total).
  - Tabela com as ApiKeys geradas contendo:
    - Nome da chave.
    - Chave mascarada/visível com botão para copiar para a área de transferência.
    - Badges dos escopos vinculados.
    - Botão de exclusão/revogação imediata da chave com confirmação.

## requisitos funcionais
- Adicionar a aba "Authentication" e respectivo template `src/templates/fragments/tab_auth.html`.
- Endpoint web `POST /projects/{slug}/auth/settings` para salvar a modalidade de autenticação e credenciais básicas.
- Endpoint web `POST /projects/{slug}/auth/keys` para criar novas ApiKeys com escopos definidos.
- Endpoint web `DELETE /projects/{slug}/auth/keys/{key_id}` para revogar ApiKeys existentes.
- Atualização dinâmica via HTMX dos componentes da aba.

## requisitos não funcionais
- Interface responsiva alinhada com o design system existente (estilos base, badges, inputs e botões).
- Feedback visual imediato ao salvar configurações ou copiar chaves.

## critérios de aceitação
- A navegação para a aba "Authentication" carrega as configurações salvas do projeto.
- Alterar e salvar o método de autenticação atualiza imediatamente o comportamento da API do projeto.
- Criar uma nova ApiKey com escopos selecionados exibe a chave na lista com seus respectivos badges.
- Excluir uma ApiKey a remove imediatamente da tabela e revoga seu acesso na API.
- Testes automatizados cobrindo a renderização da aba e as ações de salvar configurações, criar e deletar chaves.

## casos de erro
- Envio de formulário de criação de ApiKey sem nome: exibir mensagem de validação (422).
- Envio de Basic Auth sem usuário ou senha quando este método for selecionado: exibir validação de erro (422).
- Tentativa de exclusão de chave inexistente: retornar 404.

## fora de escopo
- Estatísticas de uso por ApiKey (número de requisições por chave).
- Rate-limiting por chave.
