---
name: prospeccao-plataformas
description: Busca de demandas de projeto elétrico, laudo e perícia em plataformas de serviço (Workana, 99Freelas) e vagas PJ, gravadas na aba "Demandas em plataformas" do painel Prospecção Elétrica do Felipe. Use na tarefa agendada de terça/quinta, quando ele pedir para procurar demandas/freelas, ou para ajudar a montar a proposta de uma demanda achada.
---

# Demandas em plataformas

Contexto geral, painel e ciclo de aprendizado: skill `prospeccao-funil`. Propostas comerciais: skill `prospeccao-proposta` (modelo de proposta da FRB Gestão em Projetos).

## Onde procurar (navegador embutido do app Claude, no computador do Felipe, já logado)

| Plataforma | Página de busca | Como ler |
|---|---|---|
| Workana | `https://www.workana.com/pt/jobs?language=pt&query=<termo>` | `javascript_tool`: esperar 4 s e listar `a[href*="/job/"]` (título + link). Logado na conta do Felipe. |
| 99Freelas | `https://www.99freelas.com.br/projects?q=<termo>` | `javascript_tool`: esperar 3 s e listar `a[href*="/project/"]`, ignorando `/project/new`. Site liberado no navegador em 05/11/2026. |

Termos: `projeto elétrico`, `engenheiro eletricista`, `spda`, `laudo elétrico`, `subestação`, `fotovoltaico homologação`, `ART elétrica`, `as built elétrico`, `perícia elétrica`, `parecer técnico engenharia elétrica`.

Para cada demanda nova, abrir a página dela e ler com `get_page_text` (só leitura): resumo do que pedem (1 frase), local, quando foi publicada, quantas propostas já tem.

## O que entra

- Só o que o Felipe pode entregar: projeto elétrico BT/MT, SPDA, laudos, ART, subestação, fotovoltaico (projeto e homologação), as built, memorial, parecer/perícia técnica elétrica.
- Fora: só execução de obra no local, arquitetura/estrutural sem parte elétrica, site/marketing, programação de CLP pura, vaga CLT presencial.
- Perícia de periculosidade/insalubridade: fora (CLT art. 195, exclusiva de engenheiro ou médico do trabalho).
- Demanda com mais de 30 dias ou já encerrada: fora.

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
