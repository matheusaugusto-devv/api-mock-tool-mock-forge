# specs/07_add_endpoints_tab.md

# feature: add_endpoints_tab

Adicionar aba Endpoints na tela Workspace para criar, editar ou excluir endpoints

## requisitos
- A aba precisa ter um botão "Add" e uma tabela com os endpoints existentes
- Nas linhas da tabela deve existir botões para editar ou excluir aquele endpoint
- Escrever o arquivo `README.md` com guia rápido de instalação e exemplos de uso.

## regras de negócio
- A execução da CLI sem parâmetros deve iniciar o servidor na porta 8000 e abrir o navegador automaticamente no Dashboard.
- Encerrar o processo via terminal (SIGINT / Ctrl+C) deve fechar as conexões com o SQLite de forma graciosa.

## critérios de aceitação
- Testes unitários para validação dos argumentos da CLI.
- Script de build automatizado gerando o binário executável no diretório `dist/`.
- Validação da instalação e execução do pacote em um ambiente virtual limpo.