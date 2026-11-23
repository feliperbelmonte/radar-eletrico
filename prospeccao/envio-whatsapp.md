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
- 2026-11-12 — 08h56 a extensão do Chrome não estava conectada (tools existiam, `list_connected_browsers` vazio): notifiquei e encerrei; o Felipe pediu para rodar de novo e às ~09h05 conectou. 15 enviadas, 1 sem WhatsApp (B&b). Lições:
  - O aviso de número sem WhatsApp agora é "O número … não está no WhatsApp." (não "inválido"): cheque os dois textos.
  - Pule telefone com cara de placeholder (ex.: final 990000000 — Vitorio Karan) e avise no fim.
  - Enquanto eu enviava, outra execução fez a triagem às 09h34 (documentos `triagem` com sufixo do dia) e a aba caiu em "aberto em outra janela" às ~09h36. Antes da varredura, liste a coleção `triagem`: se já houver triagem de hoje, confira só mensagens chegadas depois dela.
  - Para a varredura, ler o `#pane-side` rolando de 400 em 400 px e casar pelos 7 últimos dígitos (contatos aparecem como "+55 41 9975-0339", sem o 9) funciona; parar só depois de 4 rolagens sem linha nova.
- 2026-11-13 (agendada, 08h55–09h40) — 16 enviadas (Zarpelon saiu depois do limite, às 09h37), 1 sem WhatsApp (Ivo Gomes). Pulei: Agencia Regional de Tubarao (órgão público), Vitorio Karan (telefone placeholder) e "Rua Benjamin Constant, 510" (nome é endereço, não empresa). Lições:
  - O WhatsApp guarda o texto como rascunho na conversa: quando passo para a próxima, o Felipe às vezes envia depois clicando na conversa da lista (Monteiro, Christmann, Gerlach, Bonança, Zarpelon). Detectar o envio só pelo trecho próprio da empresa nas linhas do #main (sem exigir caixa vazia) e, no fim, reconferir o histórico de todas as "não enviadas" e a lista lateral (`#pane-side`) antes de dar o número final.
  - Durante a espera, o cabeçalho do #main pode mostrar outra conversa (o Felipe clicou numa da lista para enviar o rascunho): não navegue enquanto o cabeçalho não for o número da empresa atual por mais de alguns segundos.
  - Triagem já feita de manhã (08h51): bastou ler as ~25 primeiras linhas do `#pane-side` (ordem por recência) e abrir só quem respondeu depois disso — 3 respostas das enviadas de hoje (2 sem interesse, 1 "obrigado").
- 2026-11-16 (agendada 08h55 sem Chrome conectado; rodada às 10h37 a pedido do Felipe) — 15 enviadas e entregues + Wind (ficou com relógio/pendente desde 10:53), 4 sem WhatsApp (Instal-tec, Libra, Queiroz Telles, Mino Xavier). Pulei por telefone placeholder: Siaa e Arquipar (números de mentira, só 9s e 0s). Não enviadas (rascunho ficou no WhatsApp): Construtora Lf Morais, Eletro Evolution Br. Lições:
  - Uma mensagem presa no relógio (pendente) faz toda navegação cair em "Sair do site?". Com a mensagem salva no histórico (confirmei que continua na conversa depois do reload), use `navigate` com `force: true`.
  - Um só `browser_batch` por empresa: navigate sem text → JS que confere o histórico e, se limpo, faz `location.href = url com text` via setTimeout → `computer wait` de 3–4 s (sem isso o JS seguinte morre com "target navigated") → JS que espera o envio por 36 s.
  - Mensagens de perícia longas: monte a URL no JS com `encodeURIComponent(texto)` em vez de colar a URL codificada.
  - Variáveis `window.__*` somem a cada navigate: faça a varredura da lista lateral depois da última navegação, ou refaça.
- 2026-11-17 (agendada 08h56 sem Chrome conectado; rodada às 09h18 a pedido do Felipe) — 15 enviadas em ~25 min, 0 sem WhatsApp. Pulei por telefone placeholder: Siaa, Arquipar, Vitorio Karan, Mazini (só 9s/0s); por nome-endereço: "Rua Benjamin Constant, 510". Lições:
  - Abrir com texto via `location.href` dentro de `setTimeout` no JS não funcionou (caixa ficou vazia). Use 2 lotes por empresa: (1) navigate sem `text` + JS que confere o histórico; (2) se limpo, navigate com a `url` da fila (`force: true`) + espera 6 s + JS de espera.
  - O detector por `[role=row]` + caixa vazia falhou 2 vezes (Fajardo, Celso Saldanha: mensagem com relógio, o JS seguia lendo a caixa cheia). Mais confiável: `#main.innerText` sem o `footer` contendo o nome da empresa, e conferir a lista lateral antes de dar "não enviada".
  - A varredura do `#pane-side` a partir do topo perdeu as ~8 primeiras linhas (as conversas de hoje): leia as primeiras linhas antes de rolar.
- 2026-11-18 (agendada 08h55 sem Chrome conectado; rodada às 09h11 a pedido do Felipe) — 16 enviadas em ~15 min (a 16ª saiu antes de eu parar), 0 sem WhatsApp. Pulei por telefone placeholder: Siaa, Arquipar, Vitorio Karan, Mazini, Gandin (só 2s e 9s); por nome-endereço: "Rua Benjamin Constant, 510". Lições:
  - Depois de um `navigate`, o `#main` pode continuar mostrando a conversa anterior por alguns segundos (Sb Advogados): toda checagem de histórico e de envio só vale com o cabeçalho do `#main` contendo os 8 últimos dígitos do número (o cabeçalho mostra "+55 41 9956-9187", sem o 9).
  - Detector de envio confiável: algum `#main [data-pre-plain-text]` (bolha já no histórico) contendo o nome da empresa, com o cabeçalho conferido; `innerText` do `#main` menos o `footer` deu falso positivo.
  - Todo `navigate` deu "Sair do site?": use sempre `force: true`.
  - Na varredura do `#pane-side`, linhas lidas logo após a rolagem vêm vazias (só o título): para as que importam (padrão sem_resposta), role de volta devagar (0,5 tela, 400 ms) e releia até ter a prévia.
- 2026-11-19 (agendada 08h55 sem Chrome conectado; rodada às 08h57 a pedido do Felipe) — 15 enviadas em ~10 min, 1 sem WhatsApp (Cesar & Bertolin). Pulei por telefone fictício: Siaa, Arquipar, Vitorio Karan, Mazini, Gandin; por nome que não é empresa: "Rua Benjamin Constant, 510" e "Sociedade Individual de Advocacia" (sem nome próprio). Lições:
  - Um só `browser_batch` por empresa: navigate sem `text` (`force: true`) → espera 4 s → JS que confere cabeçalho/histórico e dá `throw` se já houver mensagem ou aviso de sem WhatsApp (o erro para o lote) → navigate com a `url` (`force: true`) → espera 6 s → JS de espera. Funcionou nas 16.
  - No `javascript_tool`, IIFE `async` devolve `{}`: use `await` no nível de cima (REPL), sem embrulhar em função.
  - Na varredura, a lista lateral até "12/11" coube em ~45 rolagens (3 chamadas); o resultado de JS corta em ~1500 caracteres: guarde em `window.__R` e devolva em fatias curtas.
  - (a pedido do Felipe) `envio.py fila` agora tira da fila sozinho telefone fictício (≤2 dígitos diferentes depois do DDD), nome que é endereço, nome só com termos genéricos e órgão público (`motivo_invalido`). Os 20 cadastros assim que estavam a_contatar foram marcados "pulada" no painel com o motivo.
- 2026-11-23 (agendada 08h35) — Chrome conectado; 1ª da fila (Demetrius Macei) aberta com o texto às ~08h38, e ~40 s depois a aba caiu em "O WhatsApp está aberto em outra janela" (o Felipe abriu o WhatsApp em outro lugar). Encerrei sem clicar, sem marcar e sem triagem. Na próxima execução, confira o histórico da Demetrius (send?phone sem text). Fila de hoje: 39 de perícia (escritórios de advocacia) antes das de projeto.
- 2026-11-23 (continuação a pedido do Felipe, 08h45–09h00) — 15 enviadas em ~15 min (Demetrius tinha saído às 08h37, antes da queda), 2 sem WhatsApp (Duarte, Cristo; Cochmanski & Mader). A queda "outra janela" das 08h38 coincidiu com a triagem agendada das 08h41 (documentos `triagem` com sufixo 202611230841): as duas tarefas disputam o WhatsApp Web — convém não agendar a triagem no mesmo horário dos envios. Varredura depois dos envios: só 2 linhas de hoje com resposta (Nunes & Guimaraes → futuro; Brasil Thomaz = resposta automática, ignorada) + padrão sem_resposta (Fabiano Lopes).
