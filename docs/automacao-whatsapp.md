# Prospecção Elétrica — automação do contato (WhatsApp e e-mail)

> Registrado em 29/10/2026. A conversa original sobre a automação do envio ficou numa sessão de tarefa que não está mais acessível, então este descritivo foi refeito e passa a ser a referência. Qualquer decisão nova sobre a automação deve ser anotada aqui.

## Objetivo

Deixar a prospecção o mais automática possível sem colocar em risco o número de WhatsApp do Felipe, sem violar a política do WhatsApp e sem problema com a LGPD.

## O limite que não dá para contornar

A primeira mensagem para uma empresa que nunca falou com o Felipe **não pode ser disparada por robô no WhatsApp** com segurança:

| Caminho | Por que não serve para o 1º contato |
|---|---|
| Ferramentas não oficiais (Z-API, Evolution API, Baileys, WPPConnect, extensões de "disparo", CallMeBot) | Violam os termos do WhatsApp. Envio em série para quem não tem o número salvo é o padrão que o WhatsApp detecta e bane. Perder o número é perder todos os contatos e conversas. |
| API oficial (WhatsApp Cloud API, da Meta) com modelo de marketing | A política exige opt-in (a empresa precisa ter autorizado receber mensagens). Lista da Receita não é opt-in. Denúncias derrubam a nota de qualidade e bloqueiam o número. Custa cerca de R$ 0,31–0,38 por mensagem de marketing. |
| Lista de transmissão do app | Só chega para quem salvou o número do Felipe. Para desconhecidos, não entrega. |

Conclusão: o 1º contato pelo WhatsApp continua sendo **um toque do Felipe** (abrir o link pronto e apertar enviar). Todo o resto pode ser automatizado.

## Desenho final (o máximo automatizado com segurança)

### Fase 1 — Fila diária "1 toque" (automação do Claude) — IMPLANTADA em 30/10/2026
Decisão do Felipe (29/10/2026): "vc prepara td e eu só dou o confere e mando a msg"; o painel deve ser atualizado conforme ele envia, e o Claude pergunta como está o retorno para atualizar o controle geral.

Como ficou:
- Painel: aba **Fila de hoje** (padrão ao abrir) calculada no próprio painel: follow-ups vencidos (status `contatado`, 5+ dias úteis desde `contatadoEm`, sem `followupEm`) + empresas novas `a_contatar` na ordem de prioridade até completar 15 no dia; as já enviadas hoje ficam no fim. Botão verde "Abrir no WhatsApp" marca `contatado` + `contatadoEm`; "Enviar follow-up" grava `followupEm`. Texto do follow-up: constante `FOLLOWUP_TEXTO` em `prospeccao/template.html`.
- Tarefa agendada `trig_01MFZpZoBARsPm33RxiFzMc5` "Prospecção Elétrica — fila do dia": seg–sex 08h37 (Brasília), só lê o banco e manda push com a fila do dia e os números. Não envia nada para empresas.
- Check-in dos retornos: lembrete na conversa do Felipe com o Claude (send_later, seg–sex 17h47), que lista quem foi contatado, pergunta quem respondeu, atualiza status/nota no banco do painel e reagenda o próximo dia útil.
- Tarefa semanal `trig_01HbnmhPxewzf88gA2jV27uv` (segunda 14h41) continua republicando a lista nova; os status ficam no banco e não se perdem.

Plano original:
- Tarefa agendada de segunda a sexta, ~08h40: lê o painel, separa as **15 empresas do dia** (prioridade PR → Curitiba/litoral → região de Jaraguá do Sul → resto, segundo `prospeccao.toml`) e mais os **follow-ups vencidos** (contatadas há 5 dias úteis sem resposta, máximo 1 follow-up por empresa).
- Publica no painel uma aba "Hoje" com essa fila e manda push: "Prospecção: 15 novas + 4 follow-ups prontos".
- O Felipe abre o painel no celular, toca "Abrir no WhatsApp" → enviar. Leva ~5 min por dia. O toque já marca "Contatado" e grava a data.
- Quem foi marcado "Sem interesse" nunca volta para a fila.

### Fase 2 — Número dedicado (ação do Felipe, uma vez)
- Chip separado só para a prospecção, com o **WhatsApp Business** (app, grátis). Se der problema, o número pessoal fica intacto.
- Perfil completo: nome "Felipe Belmonte — Projetos Elétricos", foto, descrição curta, e-mail, catálogo com os serviços (projeto elétrico BT/MT, SPDA, laudo, fotovoltaico, subestação).
- Configurar mensagem de ausência (fora do horário comercial) e respostas rápidas (`/preco`, `/portfolio`, `/prazo`) com os textos da skill `prospeccao-resposta`.
- "Aquecer" o número: 1–2 semanas de uso normal antes de começar; começar com 10–15 conversas novas por dia e só subir se não houver aviso de bloqueio.

### Fase 3 — Respostas com ajuda automática
- Quando a empresa responde, a conversa passa a ser iniciada por ela (aí não há problema de opt-in).
- Caminho simples (recomendado agora): o Felipe cola a resposta aqui no chat; o Claude rascunha a resposta (skill `prospeccao-resposta`) e atualiza o status no painel.
- Caminho avançado (opcional, só se o volume justificar): ligar o número dedicado à Cloud API oficial no modo coexistência (app e API no mesmo número; confirmar disponibilidade na hora de configurar). Respostas dentro da janela de 24 h após a mensagem da empresa são gratuitas. Um webhook (ex.: Cloudflare Worker grátis) recebe as mensagens, atualiza o painel para "Respondeu" e manda push com o rascunho da resposta. O envio da resposta comercial continua aprovado pelo Felipe: preço, prazo e escopo nunca saem sem ele.

### Fase 4 — Canal 100% automático: e-mail (opcional)
- A base da Receita traz e-mail de muitas empresas. Para contato B2B, um e-mail curto, identificado, com motivo claro e opção de descadastro tem base mais segura na LGPD (legítimo interesse) do que WhatsApp frio.
- GitHub Actions envia ~20 e-mails por dia de um endereço próprio (ex.: contato@ do domínio da FRB, não o Gmail pessoal), com SPF/DKIM configurados, link/resposta "não quero receber" que marca "Sem interesse" automaticamente.
- Quem responder o e-mail com interesse vai para o WhatsApp normalmente.

## Proteções (valem para todas as fases)
- Nunca disparo em massa, nunca ferramenta não oficial, nunca mensagem para quem pediu para parar.
- Mensagem sempre identificada (nome, CREA-PR, FRB Gestão em Projetos) e com saída fácil ("se não fizer sentido, me avisa que não mando mais").
- Horário comercial, dias úteis.
- Telefones e e-mails da lista continuam só no painel criptografado; nunca em mensagens de notificação, issues ou commits.
- Golpe/fraude: o Felipe nunca envia documento pessoal, código de verificação ou pagamento antecipado para "cliente" novo; contrato e ART só depois do primeiro pagamento (mesmo padrão dos contratos que ele já usa).

## Checklist para concluir

| # | Quem | O quê |
|---|---|---|
| 1 | Felipe | Comprar chip dedicado e instalar o WhatsApp Business |
| 2 | Felipe | Preencher perfil, catálogo, mensagem de ausência e respostas rápidas (o Claude escreve os textos) |
| 3 | Felipe | Usar o número normalmente por 1–2 semanas (aquecimento) |
| 4 | Claude | Criar a aba "Hoje" no painel e a tarefa agendada diária da fila (Fase 1) |
| 5 | Claude | Atualizar `prospeccao.toml` com o número/assinatura novos |
| 6 | Felipe | Começar: 10–15 novas por dia + follow-ups da fila |
| 7 | Claude | Revisão quinzenal do funil (skill `prospeccao-funil`) e ajuste dos textos |
| 8 | Ambos | Decidir depois do 1º mês se vale a Fase 3 avançada ou a Fase 4 (e-mail) |
