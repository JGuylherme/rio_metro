# Publicar a versão 2.2.0 e pedir reavaliação

O pacote foi gerado e validado localmente. O código ainda não foi enviado ao GitHub;
a release e os pedidos no Registry ainda não foram publicados.

## 1. Conferir os arquivos prontos

Na pasta do projeto:

```sh
cd /Users/guylherme/Documents/github/rio_metro

git status --short
```

Arquivos principais:

- `dist/RIO.zip`: mapa 2.2.0, já validado.
- `dist/manifest.json`: compatibilidade `>=1.7.0 <1.7.2`, incluindo 1.7.1.
- `preview.png`: prévia atualizada dos dados; não é captura dentro do jogo.
- `validation_report.json`: resultado da validação integral.
- `REGISTRY_DESCRIPTION.md`: descrições prontas.
- `QUALITY_REVIEW.md` e `data-quality.proposed.json`: pedido técnico de reavaliação.
- `METHODOLOGY.md` e `reports/quality/`: metodologia e evidências.

Os 21 testes automatizados passaram. A validação conferiu os 676 pares municipais,
as capacidades modeladas, os arquivos do mapa e o ZIP. Ainda é necessário conferir
visualmente o mapa dentro do jogo antes de anunciar testes de gameplay.

## 2. Subir o código no seu repositório

O remoto configurado é `JGuylherme/rio_metro`, branch `master`.

```sh
git add -A
git diff --cached --stat
git commit -m "Upgrade Rio Metropolitan to 2.2.0 with RAIS CNEFE and constrained OD"
git push origin master
```

Confira o resumo antes do commit. `data/`, `build/`, `dist/`, `.venv/` e logs já são
ignorados: o ZIP grande será enviado como **asset de release**, não como arquivo
normal do Git. Os scripts, fontes congeladas pequenas, documentação e relatórios
agregados devem acompanhar o código para permitir a revisão.

Não é necessário recriar a geometria. Para reproduzir a geração no futuro:

```sh
.venv/bin/pip install -r requirements.txt
.venv/bin/python -u fetch_quality_sources.py
.venv/bin/python -u prepare_quality_sources.py
.venv/bin/python -u build_rio.py --quality-upgrade
.venv/bin/python -m unittest discover
.venv/bin/python -u validate_rio.py
```

O último comando também recria e testa o ZIP. Ele verifica os dados gerados;
não substitui um teste visual dentro do jogo.

## 3. Publicar a GitHub Release

Abra [Nova release](https://github.com/JGuylherme/rio_metro/releases/new).

1. Crie a tag **`v2.2.0`**, apontando para o commit enviado à `master`.
2. Título: **Rio Metropolitan 2.2.0**.
3. Cole as notas de `RELEASE_NOTES.md` na descrição.
4. Anexe **`dist/RIO.zip` e `dist/manifest.json` separadamente**, com esses nomes.
5. Opcionalmente anexe `dist/quality-evidence.zip` e `preview.png`.
6. Publique como release normal, não como rascunho nem pré-release.

Se você preferir a CLI e já estiver autenticado:

```sh
gh release create v2.2.0 dist/RIO.zip dist/manifest.json dist/quality-evidence.zip \
  --repo JGuylherme/rio_metro --target master \
  --title "Rio Metropolitan 2.2.0" --notes-file RELEASE_NOTES.md
```

O arquivo correto é `dist/RIO.zip`, que inclui a demanda especial. A pasta `build/`
contém a representação intermediária da população censitária.

A correção de compatibilidade só chega ao Railyard depois que os novos assets são
publicados e a versão é processada pelo Registry. Se a mensagem de incompatibilidade
persistir, confirme se o Railyard está oferecendo **2.2.0**, e se o `manifest.json`
separado está presente nessa release. Não altere a faixa para versões futuras que
não foram verificadas.

## 4. Atualizar descrição e tags do mapa existente

Abra [Update Existing Map Metadata](https://github.com/Subway-Builder-Modded/registry/issues/new?template=update-map.yml).

- **Map ID:** `rio-metropolitan`.
- **Description:** descrição curta de `REGISTRY_DESCRIPTION.md`.
- **Data Source:** `IBGE Census 2022; CNEFE 2022; RAIS 2024; CEMPRE 2024; PNAD Continua 2026Q2; Census 2010 historical OD; OpenStreetMap; Overture; GMRT`.
- **Methodology:** resumo técnico de `REGISTRY_DESCRIPTION.md`, com link para
  `https://github.com/JGuylherme/rio_metro/blob/v2.2.0/METHODOLOGY.md`.
- **Special Demand:** marque `airports`, `entertainment`, `ferries`, `hospitals`,
  `parks`, `schools`, `universities`.
- Use a nova prévia quando atualizar a galeria.
- Deixe os campos que não deseja alterar em branco.

Praias e shoppings usam `entertainment`. Atualizar tags/metadados **não altera a nota**.
O próprio [formulário oficial](https://github.com/Subway-Builder-Modded/registry/blob/main/.github/ISSUE_TEMPLATE/update-map.yml)
orienta enviar novas respostas de qualidade quando os dados mudam.

## 5. Pedir uma nova avaliação de Data Quality

Abra [Map Data Quality](https://github.com/Subway-Builder-Modded/registry/issues/new?template=data-quality.yml).
Título sugerido: **[Data Quality]: rio-metropolitan — v2.2.0 re-review**.

| Campo | Resposta |
| --- | --- |
| Map ID | `rio-metropolitan` |
| Same methodology? | `No — new or different methodology` |
| Same-Methodology Sample | Em branco |
| Where do your job numbers come from? | `A government business register — jobs counted at each company's registered address` |
| Smallest area for job numbers | `Whole cities or municipalities` — classificação conservadora; pedir análise de CEP/ADM4 nas notas |
| Job placement | Deixe em branco e explique o híbrido CNEFE + Overture + calibração RAIS nas notas |
| What do your population numbers count? | `Everyone of working age (roughly 15–64)` — esclarecer que usamos os intervalos completos de **15–59** |
| Smallest population area | `Individual buildings or census blocks` — são setores, não contagens por prédio |
| Population placement | Deixe em branco e explique setores preservados com localização em unidades residenciais CNEFE |
| Commute-flow data | `Partial — per-area totals plus how far or where trips tend to go` |
| Smallest commute-flow area | `Whole cities or municipalities` |

**Por que dois campos ficam em branco?** O formulário não oferece exatamente a
combinação de endereços oficiais CNEFE, footprints OSM/Overture e intensidades
calibradas. Marcar “official building footprints” atribuiria uma precisão que não
existe. O formulário permite campos em branco e avaliação manual; a pontuação
provisória pode ficar incompleta até o revisor classificar esses campos.

No campo **Methodology**, cole a seção técnica de `REGISTRY_DESCRIPTION.md` e o
texto de `REVIEW_REQUEST.md`. Inclua estes links permanentes, depois de publicar a tag:

- `https://github.com/JGuylherme/rio_metro/releases/tag/v2.2.0`
- `https://github.com/JGuylherme/rio_metro/blob/v2.2.0/METHODOLOGY.md`
- `https://github.com/JGuylherme/rio_metro/blob/v2.2.0/QUALITY_REVIEW.md`
- `https://github.com/JGuylherme/rio_metro/blob/v2.2.0/data-quality.proposed.json`
- `https://github.com/JGuylherme/rio_metro/tree/v2.2.0/reports/quality`
- `https://github.com/JGuylherme/rio_metro/blob/v2.2.0/validation_report.json`

No campo **Data Source Links**, use os endereços da lista `sources` de
`data-quality.proposed.json`. Cite as avaliações anteriores #10682 e #10680 como
histórico, indicando que o pedido trata da implementação nova.

Peça avaliação da granularidade efetiva entre ADM3 e ADM4, **sem afirmar que CEP é
emprego observado por prédio**. Informe que 85,3% dos vínculos têm suporte por CEP,
14,7% usam fallback municipal, e parte dos CEPs cobre áreas extensas. O JSON proposto
mantém ADM3 conservador e deixa a revisão desse ponto ao mantenedor.

A matriz entre destinos usa o **Censo 2010 como referência histórica**; o Censo 2022
fornece a contenção local. Não selecione matriz completa enumerada nem descreva
os pares históricos como observações de 2022.

Se o bot apresentar erro de validação, corrija a issue e comente `revalidate`, conforme
[o formulário oficial](https://github.com/Subway-Builder-Modded/registry/blob/main/.github/ISSUE_TEMPLATE/data-quality.yml).
Depois acompanhe o PR gerado e responda às perguntas do mantenedor. Só a confirmação
do revisor muda a classificação pública.

## Expectativa de nota

A versão anterior está em aproximadamente **0,33 / Low**. Os cenários locais são
**0,51–0,64**, dependendo da classificação aceita. A leitura conservadora continua
**Medium**; **High é uma possibilidade, não um resultado já concedido**.
