# specs/02_dashboard_ui.md

# feature: dashboard_htmx_e_workspace

Desenvolver a interface gráfica server-driven utilizando FastAPI, Jinja2 e HTMX, permitindo a gestão de projetos e a criação dinâmica de schemas sem recarregar a página.

## requisitos
- Criar a página principal (API Hub) listando os projetos criados com opção de busca.
- Criar o formulário de criação de projeto via HTMX (`hx-post`), redirecionando para o Workspace do projeto após o sucesso.
- Desenvolver o Workspace com navegação por abas reativas (`hx-get` mantendo o estado da URL).
- Implementar o Schema Builder: formulário HTMX para adicionar recursos/tabelas e definir colunas/tipos.

## regras de negócio
- O formulário de criação de recurso deve impedir nomes de colunas duplicados no mesmo recurso.
- Nomes de recursos devem ser sanitizados para o formato plural em minúsculas (ex: `users`, `products`).

## critérios de aceitação
- Renderização Server-Side (SSR) completa via templates Jinja2.
- Todas as ações de submissão e alteração no Schema Builder devem rodar via HTMX sem reload completo da página.
- Testes unitários para as rotas que entregam os fragmentos HTML (views HTMX).