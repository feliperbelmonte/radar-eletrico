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
- 2026-11-10 — roteiro criado. 1ª execução (10/11): 12 enviadas, 2 puladas (sem WhatsApp), ~24 min.
- 2026-11-10 (1ª execução, ~15h30) — 4 enviadas de 15. Lições:
  - Modelos de perícia vêm com "Bom dia!" fixo (sem {saudacao}); à tarde ficam errados → pulei 2 (Vitorio Karan, Del Claro). Corrigir os modelos no painel/envio.py.
  - Detectar o envio pelo texto do #main contendo um trecho próprio da empresa (ex.: "<nome> foi uma delas") com a caixa vazia; `.message-out` não achou nada e o `inicio` é igual em todas as mensagens.
  - browser_batch estoura o tempo com ~90 s; use lotes de ~50 s (5 × espera de 10 s + checagem).
  - Se aparecer "O WhatsApp está aberto em outra janela", não clique em "Usar nesta janela" (derrubaria a sessão do Felipe): encerre e avise.
  - Se a caixa esvaziar mas a mensagem não aparecer na conversa, não marque na hora, mas reconfira depois abrindo a conversa sem texto (na Engecon a mensagem tinha ido, às 15:35).
  - Git na pasta montada: precisa de permissão de exclusão (arquivos .lock) e `git -c core.autocrlf=true` (senão todo arquivo aparece modificado por CRLF).
- 2026-11-10 (tarde, com o Felipe) — regras novas:
  - Meta é 15 ENVIADAS por dia (sem WhatsApp/sem envio não conta): siga pela fila (`fila --meta 45`) até completar 15.
  - ANTES de abrir com texto, abra `web.whatsapp.com/send?phone=…` SEM `text` e conte as mensagens do #main (ignore o aviso de criptografia). Se já houver mensagem: não abra com texto; se for a nossa de hoje, marque contatado (conta nas 15); senão pule.
  - O painel pode não saber de envios feitos pelo Felipe (ele envia rápido, às vezes depois que a Claude já passou para a próxima) — sempre confira o histórico.
  - Se o Felipe trocar de conversa na aba (caixa com outro texto), pare de ler/navegar e espere ele dizer "continua".
- 2026-11-11 (agendada, 08h55) — 1 enviada (E S Eletricidade). Na 2ª (Siloto), depois de ~3 min com o texto na caixa, a aba caiu em "O WhatsApp está aberto em outra janela" (o Felipe abriu o WhatsApp em outro lugar): encerrei sem clicar, sem triagem. Lições:
  - `javascript_tool` estoura em 45 s (CDP): laço de espera de no máximo ~36 s (9 × 4 s) por chamada.
  - Pule também nomes que não são empresa privada (ex.: "Agencia Regional de Tubarao", órgão público) — avise no fim.
  - Siloto ficou sem marcar: na próxima execução a checagem de histórico (send?phone sem text) mostra se ele enviou pela outra janela.
- 2026-11-11 (continuação com o Felipe, ~09h15–10h05) — 15 enviadas (pulada: Agencia Regional de Tubarao, órgão público). Lições:
  - Mesmo com o limite de 4 min, ele às vezes envia depois (Averon, Tda): no fim, antes de puxar novas da fila, reabra as "não enviadas" sem `text` e confira o histórico — se a nossa mensagem estiver lá, marque contatado (conta nas 15).
  - Ao conferir o histórico, ignore também o aviso de "mensagens temporárias" (não é mensagem da empresa).
  - `triagem.py cnpjs` quebrava (faltava `--agora` no subcomando) — corrigido.
  - Varredura: a busca pelo nome não acha as empresas de 03–04/11 marcadas "BUSCAR PELO NOME" (a mensagem não citava o nome igual ou foi por outro canal): pule, sem aplicar sem_resposta.
