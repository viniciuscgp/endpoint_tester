# EndpointTester

Aplicativo desktop em Python/Tkinter para testar e organizar endpoints HTTP sem depender de plugins ou navegador. Permite salvar configurações, enviar requisições via `curl` e manter preferências de layout.

## Requisitos
- Python 3.x
- `curl` instalado e disponível no PATH

## Como executar
```bash
python endpoint_tester.py
```

## Principais recursos
- Campos para Nome, URL e Método (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS).
- Headers em JSON ou linhas `Chave: Valor`; Body em texto livre (enviado como `--data-raw`).
- Lista de endpoints salvos com botões de adicionar e remover; largura ajustável.
- Seções (Headers, Body, Resposta/log) redimensionáveis na vertical, com fonte fixa ajustável (A+/A-) e botão “Limpar” em cada título.
- Execução via `curl` com exibição do comando, headers e corpo formatado (JSON é indentado automaticamente).
- Preferências persistidas em `ui_state.json` (geometria da janela, divisórias, tamanhos de fonte) e endpoints em `endpoints.json`.

## Uso rápido
1) Abra o app e preencha Nome, Método e URL.  
2) Headers: informe como JSON ou linhas `Chave: Valor`. Body: texto livre (opcional).  
3) Clique **Enviar** para testar (salva automaticamente) ou **Salvar** para apenas persistir.  
4) Use o painel esquerdo para selecionar endpoints gravados; `+` limpa para novo, `x` remove o selecionado.  
5) Ajuste divisórias ou fontes (A+/A-) das seções; os ajustes ficam gravados para a próxima sessão.

## Arquivos gerados
- `endpoints.json`: lista de endpoints salvos (nome, URL, método, headers, body).
- `ui_state.json`: geometria da janela, posições das divisórias e tamanhos das fontes das áreas de texto.

## Dicas
- Cabeçalhos inválidos geram erro; verifique o formato ao salvar/enviar.  
- Se `curl` não estiver disponível, instale-o no sistema para executar as requisições.
