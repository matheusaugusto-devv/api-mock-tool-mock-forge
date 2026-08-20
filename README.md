# Mock Forge

Mock Forge é uma ferramenta CLI leve e completa para criação rápida de APIs REST mock dinâmicas com interface web em HTMX, suporte a geração de dados com Faker, importação/exportação OpenAPI 3.0, streaming de logs em tempo real via Server-Sent Events (SSE) e suporte a autenticação via apiKey e Bearer token. Você cria uma api e configura conforme os requisitos do seu frontend, esta aplicação é ideal para prototipagem rápida de frontends sem ter a necessidade de contruir um backend.

---

## 🚀 Instalação Rápida

### Via `pipx` (Recomendado)
Execute sem poluir seu ambiente global do Python:

```bash
pipx run mock-forge start
```

Ou instale globalmente via `pipx`:
```bash
pipx install mock-forge
mock-forge start
```

### Via `pip`
```bash
pip install mock-forge
mock-forge start
```

### Executável Binário Isolado (PyInstaller)
Você pode gerar e rodar binários standalone sem dependência prévia do Python instalado:
```bash
python build.py
./dist/mock-forge start
```

---

## 💻 Uso da CLI

Inicie o servidor com os parâmetros padrão (porta 8000, host 127.0.0.1 e abrindo o navegador no Dashboard):

```bash
mock-forge start
```

### Opções Disponíveis

| Parâmetro | Opção Curta | Padrão | Descrição |
|-----------|-------------|--------|-------------|
| `--port` | `-p` | `8000` | Porta HTTP do servidor |
| `--host` | `-h` | `127.0.0.1` | Endereço de host para bind |
| `--db-path` | | `mock-forge.db` | Caminho do arquivo de banco SQLite |
| `--open-browser` / `--no-browser` | | `True` | Abrir automaticamente o navegador no Dashboard |

Exemplo customizado:
```bash
mock-forge start --port 3000 --host 0.0.0.0 --db-path ./my-mocks.db --no-browser
```

Para ajuda:
```bash
mock-forge --help
mock-forge start --help
```

---

## 🌐 Integração com Frontends

Mock Forge cria endpoints REST completos e dinâmicos para cada recurso sob o padrão `/api/{project_slug}/{resource}`.

### 1. Criar um registro (`POST`)
```javascript
const response = await fetch('http://localhost:8000/api/ecommerce/products', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Wireless Headphones',
    price: 99.90,
    in_stock: true
  })
});
const product = await response.json();
console.log(product);
// { id: 1, name: "Wireless Headphones", price: 99.9, in_stock: true, created_at: "...", updated_at: "..." }
```

### 2. Listar e filtrar com paginação e ordenação (`GET`)
```javascript
// Filtros, ordenação e paginação suportados diretamente via query string
const response = await fetch('http://localhost:8000/api/ecommerce/products?in_stock=true&_sort=price&_order=desc&_page=1&_limit=10');
const products = await response.json();
```

### 3. Obter por ID (`GET`)
```javascript
const response = await fetch('http://localhost:8000/api/ecommerce/products/1');
const product = await response.json();
```

### 4. Atualizar registro (`PUT`)
```javascript
const response = await fetch('http://localhost:8000/api/ecommerce/products/1', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    price: 79.90
  })
});
```

### 5. Excluir registro (`DELETE`)
```javascript
await fetch('http://localhost:8000/api/ecommerce/products/1', {
  method: 'DELETE'
});
```

---

## 🛠️ Funcionalidades Principais

- **Dynamic REST Engine**: CRUD instantâneo com SQLite para cada schema configurado.
- **HTMX Dashboard**: Gestão reativa de projetos, schemas e dados sem frameworks JS pesados.
- **Faker Generator & JSON Data Import**: Geração de lotes de dados sintéticos ou importação de arquivos `.json` diretamente para recursos no Data Explorer.
- **OpenAPI 3.0 Support**: Importação e exportação de schemas em JSON e YAML.
- **Endpoint Tester & Live SSE Logs**: Teste requisições diretamente na UI e visualize logs em tempo real.
- **Graceful Shutdown**: Encerramento seguro de conexões SQLite via SIGINT (`Ctrl+C`).
- **Spec-Driven Development (SDD)**: Desenvolvido rigorosamente com base em especificações formais (`/specs`), garantindo alta cobertura de testes unitários e arquitetura desacoplada.
