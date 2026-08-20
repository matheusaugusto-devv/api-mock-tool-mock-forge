# specs/06_add_json_file_support.md

# feature: add_json_file_support

Alterar importação de dados para as rotas DE: schema/project PARA: arquivo json com dados em Data Explorer

## requisitos
- Utilizar dados de arquivo json para popular o resource selecionado 
- O backend deve fazer o parse de json para o formato aceito no SQLite
- Adicionar feedback de erro em casos de falha.
- Escrever o arquivo `README.md` com guia rápido de instalação e exemplos de uso.

## regras de negócio
- A execução da CLI sem parâmetros deve iniciar o servidor na porta 8000 e abrir o navegador automaticamente no Dashboard.
- Encerrar o processo via terminal (SIGINT / Ctrl+C) deve fechar as conexões com o SQLite de forma graciosa.

## critérios de aceitação
- Testes unitários para validação dos argumentos da CLI.
- Script de build automatizado gerando o binário executável no diretório `dist/`.
- Validação da instalação e execução do pacote em um ambiente virtual limpo.