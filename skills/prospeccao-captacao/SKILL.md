---
name: prospeccao-captacao
description: Etapa de captação da prospecção do Felipe — escolher quais empresas abordar, ajustar a mensagem inicial de WhatsApp, cadência diária e follow-up. Use quando ele for começar a mandar mensagens, pedir ajuda com a abordagem inicial, quiser mudar a lista de empresas ou os textos, ou perguntar o que fazer com quem não respondeu.
---

# Captação — do "a contatar" ao "contatado"

Contexto geral, painel e ciclo de aprendizado: skill `prospeccao-funil`.

## Como funciona hoje

- A lista vem do painel Prospecção Elétrica (https://claude.ai/artifact/BAJojSBRshrr1MRC4Eoujg). Cada empresa tem um de 3 modelos de mensagem (campo `modelo`), escolhido pelo CNPJ, com nome da empresa, cidade e atividade.
- Felipe abre a aba "Fila de hoje" (15 novas + follow-ups vencidos), confere, clica em "Abrir no WhatsApp" ou "Enviar follow-up" e envia. O clique já marca "Contatado" (ou grava `followupEm`). Push da fila seg–sex 08h37; check-in dos retornos com o Claude seg–sex 17h47 (ver `docs/automacao-whatsapp.md`).
- Textos, segmentos, porte, região e prioridade ficam em `prospeccao.toml` no repositório `radar-eletrico`. Mudança permanente no texto vai lá, não só numa conversa.

## Regras

- Envio manual, uma empresa por vez. Nada de disparo em massa, listas de transmissão ou ferramentas de automação de WhatsApp.
- Meta inicial: 15 novas conversas por dia. Começar devagar protege o número contra bloqueio; aumentar só se não houver sinais de bloqueio e se ele der conta das respostas.
- Mensagem curta, em primeira pessoa, sem cara de anúncio: quem é, por que está escrevendo para *aquela* empresa, o que oferece (só projeto, sem concorrer na execução), uma pergunta simples, saída fácil.
- Quem pedir para não receber mais: marcar "Sem interesse" na hora e nunca mais escrever.
- Follow-up: no máximo 1, depois de 4 a 5 dias úteis sem resposta, curto e sem cobrança (ex.: "Oi, só retomando a mensagem de semana passada: se em algum momento precisarem de projeto elétrico, fico à disposição."). Sem resposta depois disso: deixar quieto.
- Não prometer nada que dependa de ART fora do PR sem confirmar a exigência do CREA local.

## Ao ajudar o Felipe nesta etapa

- Para ajustar um texto: manter os campos `{nome} {registro} {empresa} {cidade} {atividade}`, o tom e o tamanho; mostrar a versão final pronta para colar no `prospeccao.toml`.
- Para escolher onde focar: olhar as lições abaixo e os números por segmento/região (procedimento na `prospeccao-funil`).
- Sugestões que valem testar (ainda não são lições): perfil do WhatsApp Business com foto, descrição curta e lista de serviços; mandar em horário comercial; personalizar a primeira linha quando ele conhecer a empresa.

## Lições aprendidas

<!-- Formato: - AAAA-MM-DD — lição. Evidência: ... [hipótese | confirmada] -->
- (ainda nenhuma — a primeira revisão do funil acontece depois dos primeiros contatos)
