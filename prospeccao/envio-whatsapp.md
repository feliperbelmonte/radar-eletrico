# Roteiro — abrir as conversas novas do dia no WhatsApp Web

> Leia inteiro antes de abrir o Chrome. Decisão do Felipe (10/11/2026): a Claude abre no Chrome dele cada conversa nova com a mensagem já escrita na caixa de texto; **ele aperta Enter**. Só empresas nunca contatadas (sem follow-up, sem retomada). Mensagem: o texto do painel (modelo 4), com "Bom dia/Boa tarde/Boa noite" pelo horário de Brasília.

## Regras que não mudam

- **Quem envia é o Felipe.** Nunca aperte Enter, nunca clique no botão de enviar, nunca simule tecla. Você só abre a conversa (a URL já coloca o texto na caixa).
- Uma empresa por vez, na mesma aba (o WhatsApp Web não aceita duas abas abertas).
- Não edite o texto da mensagem; se algo parecer errado (nome estranho, cidade errada), pule a empresa e avise no fim.
- Não abra nem leia outras conversas.
- Nenhum telefone ou e-mail em notificação, commit ou mensagem final.

## Passo a passo

1. **Dados:**
   - `Artifact` action `read`, url `https://claude.ai/artifact/BAJojSBRshrr1MRC4Eoujg`, `path: "index.html"` → arquivo local com a lista (não leia; o script lê).
   - `ArtifactData` action `list`, coleção `status`, `query.limit` 1000, `out_dir` = `<pasta>/db` (siga `next_cursor`).
   - `python prospeccao/envio.py fila --painel <index.html> --status <pasta>/db/status` → lista numerada e o arquivo `<pasta>/db/fila_envio.json` com `url`, `inicio` (40 primeiros caracteres da mensagem) de cada uma. Se o script estiver no computador e o banco na nuvem (ou o contrário), copie os arquivos para o mesmo lado antes.
   - Lista vazia: notifique "Prospecção: as 15 de hoje já foram enviadas" e encerre.
2. **Avisar que começou** (PushNotification, status proactive): "Prospecção: abrindo as <n> conversas de hoje no Chrome — é só dar Enter em cada uma."
3. **Para cada empresa, em ordem** (Claude in Chrome, uma aba só, de preferência a do WhatsApp Web se já existir):
   1. `navigate` para a `url` (web.whatsapp.com/send?phone=…&text=…). Espere a conversa carregar (até 25 s).
   2. Se aparecer "número de telefone compartilhado por url é inválido" (ou equivalente): marque como pulada (passo 5 com `--pulada "sem WhatsApp"`) e vá para a próxima.
   3. Confira, lendo a página (JavaScript ou `get_page_text`), que a caixa de mensagem contém o `inicio` da mensagem. Se a caixa estiver vazia, recarregue a URL uma vez; ainda vazia, pule e anote.
   4. **Espere o Felipe enviar:** a cada 4 s, verifique se a caixa de mensagem ficou vazia e se a última mensagem enviada (bolha de saída, `.message-out`) contém o `inicio`. Limite: 4 min por empresa.
      - Enviou → passo 5 (contatado) e próxima.
      - Passou o limite sem enviar → não marque nada, siga para a próxima e anote "não enviada".
      - Se o Felipe fechar a aba ou o Chrome parar de responder: encerre e vá ao passo 6.
4. Entre uma empresa e outra não precisa esperar além do carregamento.
5. **Marcar no painel:** `python prospeccao/envio.py marcar --painel <index.html> --status <pasta>/db/status --cnpj <cnpj> --saida <pasta>/marcar` → imprime `doc_id` e `file_path`. Grave com `ArtifactData` action `set`, coleção `status`, esse `doc_id` e `file_path`. Se `existe` for true (ou o set for recusado por versão), faça `get` do documento e repita o `set` com `if_version` = a versão lida.
6. **Varredura (pedido do Felipe, 10/11/2026):** com o mesmo WhatsApp Web aberto, faça a triagem do dia seguindo `prospeccao/triagem-whatsapp.md` do passo 1 ao 4 (baixe de novo a coleção `status`, porque ela mudou com os envios; reaproveite o `index.html`). Ela classifica no controle: sem interesse → descartado, "vou deixar anotado" → contato futuro em 30 dias, sem resposta em 5 dias úteis → sem resposta.
7. **Fim** (PushNotification, uma notificação só): "Prospecção [dia/mês]: <x> enviadas de <n> (<y> sem WhatsApp, <z> não enviadas). Triagem: <resumo do triagem.py gravar>. Destaque: <empresa — motivo>. Painel: https://claude.ai/artifact/BAJojSBRshrr1MRC4Eoujg"

## Lições (atualize aqui)

<!-- - AAAA-MM-DD — o que mudou e por quê -->
- 2026-11-10 — roteiro criado; primeira execução ainda não feita.
