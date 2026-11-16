# Workana — fila de propostas (desde 16/11/2026)

> Tarefas: `trig_01YF5Y5vQwziDM2dueEhNnf3` "Prospecção Elétrica — demandas em plataformas" (todo dia por volta das 9h — 08h58, navegador embutido) e `trig_01CxCGHuYv6wiZZouvL9fYeD` "Workana — enviar propostas da fila" (seg–sex por volta das 10h — 09h58, Chrome do Felipe, vinculada ao computador dele).
> Dados e histórico: coleção `demandas` do banco do painel Prospecção Elétrica (https://claude.ai/artifact/BAJojSBRshrr1MRC4Eoujg), aba "Demandas em plataformas".

## Histórico de decisões (conversa de 16/11/2026)

- Cadastro de freelancer aprovado. Escopo: só projeto/serviço feito de casa, só Brasil, sem arquitetônico (recebe pronto), trabalha em BIM no QiBuilder, aceita arquivos em qualquer formato.
- Propostas no padrão FRB: apresentação com formação e competências (sem WEG/Ultramaq, sem "CREA ativo"), escopo, valor e prazo, não incluso, perguntas ao cliente, cláusula de atualização se o escopo mudar, validade de 5 dias corridos, assinatura FRB. Horas e hora técnica servem só para precificar; não aparecem para o cliente.
- Preço coerente com o serviço (hora técnica de referência R$ 130, guia ABEE-SE 2026), mesmo acima do teto do cliente. A Workana desconta comissão do valor que o cliente vê (≈20% até ~R$ 1.750, ~10% na faixa seguinte e menos em valores altos): o valor lançado é ajustado até "Você vai receber" bater com o líquido que o Felipe quer.
- ART: CREA-PR; obra em outro estado → "mediante visto no CREA do estado, taxas por conta do contratante". Sem PVsyst: estudos FV/BESS com PVGIS + planilha.
- Valor da hora no perfil da Workana: R$ 130 (exigido pela plataforma para propor).
- Envio: a Workana pede CAPTCHA a cada proposta → o Claude preenche no Chrome e o Felipe confere, faz o CAPTCHA e clica em "Enviar orçamento".
- Limite: conta gratuita bateu o "limite semanal de contatos" depois de 2 propostas (16/11). Decisão: fila com histórico; quando o limite renova, o Claude atualiza as propostas da fila e deixa as 2 melhores prontas no Chrome; e assim por diante, semana a semana.

## Estado em 16/11/2026

| Demanda | Status | Cliente vê | Líquido |
|---|---|---|---|
| Edifício multifamiliar Bombinhas/SC (elétrico + telecom + entrada coletiva Celesc) | enviada 16/11 | R$ 17.950 | ~R$ 16.011 |
| Usina híbrida solar + BESS 20 MW | enviada 16/11 | R$ 4.420 | ~R$ 3.804 |
| Pontes rolantes (fila #1) | fila | R$ 3.980 | ~R$ 3.408 |
| Edifício de 3 andares (fila #2) | fila | R$ 5.980 | ~R$ 5.208 |
| SPDA classe III (fila #3) | fila | R$ 1.980 | ~R$ 1.608 |

Lavanderia comercial Enel SP: pulada pelo Felipe (anúncio de agosto, sem propostas).

## Passo a passo

1. **Diário ~9h (08h58)** — busca Workana (JSON `results-initials`, `country=BR`) e 99Freelas; filtra escopo home office; grava as novas. As da Workana entram com status `fila`, proposta redigida, `valorLiquidoAlvo`, `valorCliente` estimado, `prazo`, `prioridade` e `historico`.
2. **Seg–sex ~10h (09h58)** — sincroniza o que o Felipe enviou (Meus projetos → status `proposta`, `enviadoEm`); se a semana já tem 2 enviadas, para. Revalida a fila (encerradas → `descartada`), reordena, testa o limite abrindo o formulário da prioridade 1. Limite livre → preenche até 2 propostas em abas do Chrome (valor ajustado pelo "Você vai receber", texto, prazo, aceite, habilidade) e avisa por push. Nunca clica em enviar nem resolve CAPTCHA.
3. **Felipe** — confere as abas, faz o CAPTCHA e envia. Abas da Workana podem recarregar e perder o texto: nesse caso, pedir no chat para preencher de novo (o texto está no banco).

## Status da coleção `demandas`

`nova` (99Freelas ou ainda sem proposta) · `fila` (proposta pronta aguardando limite) · `proposta` (enviada) · `ganha` · `descartada`. Campos de fila: `prioridade`, `valorLiquidoAlvo`, `valorCliente`, `valorLiquido`, `prazo`, `proposta`, `historico[]`, `enviadoEm`, `propostaPreparadaEm`.

- 16/11/2026 (fim da tarde): horários ajustados a pedido do Felipe — busca diária ~9h e preparo das propostas ~10h.
