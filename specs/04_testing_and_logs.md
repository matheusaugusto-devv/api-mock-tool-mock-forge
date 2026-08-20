# specs/04_testing_and_logs.md

# feature: testador_de_endpoints_e_logs_sse

Desenvolver um playground de testes de API dentro do dashboard e um monitor de logs de requisições em tempo real utilizando a extensão SSE do HTMX.

## requisitos
- Criar o Endpoint Tester na UI: interface no estilo Postman para selecionar método, enviar payload de teste para a rota mock e visualizar o JSON de resposta e o Status Code.
- Implementar um middleware de auditoria que intercepta todas as chamadas às rotas `/api/...` e gera eventos de log.
- Criar o painel de logs em tempo real consumindo Server-Sent Events via HTMX (`hx-ext="sse"`).

## regras de negócio
- O monitor de logs deve registrar: Timestamp, Método HTTP, Path completo, Status Code da resposta e Tempo de execução (ms).
- Os eventos SSE de log devem ser filtrados apenas para o projeto ativo selecionado na tela.

## critérios de aceitação
- Testes unitários para a rota de emissão de eventos SSE (`/events/logs/{project_slug}`).
- Testes de integração para a funcionalidade do Endpoint Tester disparando chamadas para as rotas sintéticas.