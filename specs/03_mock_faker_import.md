# specs/03_mock_faker_import.md

# feature: gerador_de_mocks_faker_e_importacao

Integrar a biblioteca Faker para geração automatizada de dados de teste, criar a visualização e edição interativa de registros (Data Explorer) e permitir importação/exportação de schemas.

## requisitos
- Mapear tipos do Schema Builder para geradores do Faker (ex: `Name` -> `faker.name()`, `Email` -> `faker.email()`).
- Implementar botão "Gerar Mocks" que popula a tabela com N registros sintéticos.
- Criar o Data Explorer: tabela reativa com busca rápida e ações inline de alteração e exclusão via HTMX (`hx-post`, `hx-delete`).
- Implementar importação e exportação da configuração do projeto via JSON e OpenAPI 3.0.

## regras de negócio
- A importação de especificação OpenAPI deve criar automaticamente as tabelas e tipagens correspondentes no SQLite.
- Se um tipo Faker mapeado for inválido, o sistema deve utilizar `faker.text()` como fallback seguro.

## critérios de aceitação
- Testes unitários para o gerador de dados baseados no schema do projeto.
- Testes do parser de especificações OpenAPI 3.0 convertendo dados para o schema interno.
- Testes de exportação e importação de arquivo JSON do projeto.