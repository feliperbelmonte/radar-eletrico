---
name: prospeccao-plataformas
description: Busca de demandas de projeto elétrico, laudo e perícia em plataformas de serviço (Workana, 99Freelas) e vagas PJ, gravadas na aba "Demandas em plataformas" do painel Prospecção Elétrica do Felipe. Use na tarefa agendada diária (07h41), quando ele pedir para procurar demandas/freelas, ou para ajudar a montar a proposta de uma demanda achada.
---

# Demandas em plataformas

Contexto geral, painel e ciclo de aprendizado: skill `prospeccao-funil`. Propostas comerciais: skill `prospeccao-proposta` (modelo de proposta da FRB Gestão em Projetos).

## Onde procurar (navegador embutido do app Claude, no computador do Felipe, já logado)

| Plataforma | Página de busca | Como ler |
|---|---|---|
| Workana | `fetch('/jobs?language=pt&query=<termo>&page=<n>')` a partir de uma página da workana.com, mais `/jobs?language=pt&skills=electrical-engineering` | `javascript_tool`: extrair do HTML o atributo `results-initials='…'`, decodificar as entidades com um `textarea` e `JSON.parse`; `.results[]` traz slug, title, description, budget, postedDate, totalBids, country, skills; `.pagination.pages` dá o total de páginas (ler até 5). Link = `https://www.workana.com/job/<slug>`. Funciona sem login (valores em USD). |
| 99Freelas | `https://www.99freelas.com.br/projects?q=<termo>` | `javascript_tool`: esperar 3 s e listar `a[href*="/project/"]`, ignorando `/project/new`. Site liberado no navegador em 05/11/2026. |

Termos: `projeto elétrico`, `engenheiro eletricista`, `spda`, `aterramento`, `laudo elétrico`, `subestação`, `fotovoltaico`, `energia solar`, `homologação`, `as built elétrico`, `perícia elétrica`, `diagrama unifilar`, `luminotécnico`, `qibuilder`.

Para cada demanda nova, abrir a página dela e ler com `get_page_text` (só leitura): resumo do que pedem (1 frase), local, quando foi publicada, quantas propostas já tem.

## O que entra

- Só projetos no Brasil (decisão de 16/11/2026): na Workana, buscar com `&country=BR` e descartar item cujo `country` não seja Brasil.
- Só o que o Felipe entrega 100% em home office (decisão dele em 16/11/2026: não quer sair de casa para nada): projeto elétrico BT/MT, SPDA, aterramento, laudos documentais, ART, subestação, fotovoltaico (projeto, homologação, modelagem/estudo), as built a partir de documentos, diagramas elétricos, luminotécnico, memorial, parecer/perícia técnica elétrica feita por documentos.
- Fora: qualquer coisa que exija ir ao local (visita técnica, levantamento em campo, vistoria, instalação, montagem, comissionamento, diária presencial), execução de obra, projeto arquitetônico (ele não faz; trabalha sobre o arquitetônico pronto do cliente, em BIM no QiBuilder), estrutural/hidráulico sem parte elétrica, eletrônica/PCB, site/marketing, programação de CLP pura, vaga CLT.
- Demanda mista (ex.: elétrico + hidráulico): entra, com a observação de que ele faz só a parte elétrica.
- Perícia de periculosidade/insalubridade: fora (CLT art. 195, exclusiva de engenheiro ou médico do trabalho).
- Demanda com mais de 30 dias ou já encerrada: fora.

## Fila de propostas da Workana (desde 16/11/2026)

A conta gratuita da Workana permite 2 contatos por semana. As demandas da Workana que entram no escopo ficam com status `fila`, já com a proposta redigida (padrão FRB, skill `prospeccao-proposta`), e a tarefa "Workana — enviar propostas da fila" (seg–sex 08h25) prepara as 2 melhores no Chrome quando o limite renova; o Felipe faz o CAPTCHA e envia. Detalhes e histórico: `docs/workana-fila-de-propostas.md`.

## Como gravar no painel

Banco do painel (slug `52480dbe-d791-42d0-b2d1-ecacc497139b`), coleção `demandas`, um documento por demanda. Id: `w-<slug>` (Workana) ou `n-<número>` (99Freelas, o número no fim da URL). Se o documento já existe, não mexer (o Felipe pode ter mudado status ou nota). Campos:

`plataforma`, `titulo`, `link`, `resumo`, `local`, `publicado` (texto, ex.: "há 2 dias"), `propostas` (texto, ex.: "8 propostas"), `encaixe` (qual serviço dele atende, ex.: "SPDA + laudo"), `status` = "nova", `encontradoEm` (ISO).

Status que o Felipe usa no painel: `nova`, `proposta`, `ganha`, `descartada`.

## Regras

- Somente leitura nas plataformas: nunca enviar proposta, mensagem, candidatura ou aceitar termos sem o Felipe pedir naquela hora.
- Responder sempre pela própria plataforma. Tirar o cliente da plataforma (passar WhatsApp/e-mail antes de fechar) viola as regras delas e pode banir a conta.
- Preço: coerente com o valor do serviço (referência de mercado), não ancorado no teto do cliente — decisão do Felipe nas propostas da Workana.
- Login, verificação ou captcha: parar e avisar o Felipe (push); nunca digitar senha.

## Lições aprendidas

<!-- Formato: - AAAA-MM-DD — lição. Evidência: ... [hipótese | confirmada] -->
- 2026-11-05 — Workana e 99Freelas leem bem com `javascript_tool` no navegador embutido logado; WebFetch/WebSearch não alcançam as listagens. Evidência: teste de 05/11. [confirmada]
- 2026-11-16 — A listagem da Workana vem num JSON embutido (`results-initials`) e pode ser lida por `fetch` + `JSON.parse` sem login nem espera; varredura de 15 termos trouxe 123 demandas únicas, das quais ~20 cabem no escopo home office. Evidência: varredura manual de 16/11. [confirmada]
- 2026-11-16 — Workana exige CAPTCHA a cada proposta e tem limite semanal de contatos (2 na conta gratuita); o formulário fica em `/messages/bid/<slug>` (#Amount, #Hours, #BidContent, #BidDeliveryTime, input[name=acknowledged], habilidade obrigatória) e mostra "Você vai receber" já descontada a comissão. Abas paradas recarregam e perdem o texto. Evidência: envio de 16/11. [confirmada]
