# specs/05_cli_and_distribution.md

# feature: cli_empacotamento_e_distribuicao

Criar a interface de linha de comando (CLI) usando Typer, empacotar a aplicação para execução isolada via PyInstaller e publicar no PyPI para suporte ao `pipx`.

## requisitos
- Criar comando CLI `mock-forge start` aceitando os argumentos `--port` (padrão 8000), `--host` (padrão 127.0.0.1) e `--db-path`.
- Configurar o script de build do PyInstaller para gerar executáveis únicos para Linux, macOS e Windows.
- Configurar o pacote Python (`pyproject.toml`) para permitir a execução via `pipx run mock-forge`.
- Escrever o arquivo `README.md` com guia rápido de instalação e exemplos de uso com frontends.

## regras de negócio
- A execução da CLI sem parâmetros deve iniciar o servidor na porta 8000 e abrir o navegador automaticamente no Dashboard.
- Encerrar o processo via terminal (SIGINT / Ctrl+C) deve fechar as conexões com o SQLite de forma graciosa.

## critérios de aceitação
- Testes unitários para validação dos argumentos da CLI.
- Script de build automatizado gerando o binário executável no diretório `dist/`.
- Validação da instalação e execução do pacote em um ambiente virtual limpo.