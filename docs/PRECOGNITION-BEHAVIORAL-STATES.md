# Precognição como inferência comportamental: estados, gatilhos e validação

Este documento traduz relatos subjetivos de “pressentir o futuro” em hipóteses computacionais que o PreCog pode investigar. O objetivo é antecipar estados e comportamentos prováveis a partir de experiências anteriores, contexto temporal e sinais observáveis — não afirmar precognição paranormal nem tratar uma sensação subjetiva como prova de que um evento futuro foi conhecido.

## 1. A distinção central

Na psicologia cotidiana, “pareceu que eu sabia o que aconteceria” pode surgir de processos diferentes:

- **Inferência implícita:** o cérebro aprende regularidades e combina pistas sem que a pessoa consiga explicar conscientemente cada passo.
- **Previsão perceptiva:** o sistema nervoso usa contexto e expectativas para interpretar sinais incompletos e antecipar o que vem a seguir.
- **Interocepção e afeto:** sinais corporais e estados emocionais podem influenciar a percepção de risco ou relevância; a sensação é um dado sobre a experiência, não necessariamente uma leitura correta do mundo externo.
- **Estresse, ansiedade e fadiga:** podem alterar vigilância, atenção, memória e avaliação de ameaças. O efeito não é sempre uma melhora da previsão: também pode aumentar falsos alarmes e estreitar a atenção.
- **Aprendizagem por consequências:** decisões e ações mudam o ambiente, de modo que uma expectativa pode contribuir para produzir o resultado esperado.
- **Memória reconstrutiva e vieses:** depois do resultado, lembranças vagas podem parecer mais específicas; acertos marcantes são mais fáceis de recordar do que erros e previsões que não se concretizaram.

Esses mecanismos oferecem explicações plausíveis para algumas experiências de pressentimento. Não demonstram que a pessoa acessou informação futura. Para o PreCog, a hipótese operacional é mais restrita: **há padrões observáveis no histórico que podem melhorar a estimativa de próximos comportamentos ou resultados?**

## 2. Mapeamento de gatilhos para estados comportamentais

Os nomes de estado abaixo são uma proposta de domínio para experimentação. Não são diagnósticos psicológicos nem alegações de que o software consegue medir estados biológicos diretamente.

| Fenômeno humano possível | Estado computacional proposto | Sinais que podem ser registrados | Hipótese testável | Risco de interpretação |
|---|---|---|---|---|
| Processamento implícito de pistas | `CONTEXT_INTEGRATION` | sequência de eventos, mudanças pequenas, recorrência, sinais anteriores ao resultado | a combinação de pistas contextuais melhora a previsão em relação à taxa-base | inventar pistas retrospectivamente ou confundir correlação com causa |
| Sensação de alerta / relevância | `SALIENT_MONITORING` | mudança de frequência, novidade, urgência declarada, erro recente | eventos raros ou mudanças de contexto justificam atualizar a distribuição de resultados | novidade pode elevar alarmes sem elevar precisão |
| Estresse ou alta carga emocional declarada | `HIGH_AROUSAL_REPORTED` | somente relato voluntário explícito, ou sinal permitido com consentimento | o desempenho preditivo varia entre contextos relatados | inferir saúde mental ou emoção a partir de texto de forma determinística |
| Fadiga declarada ou contexto de baixa disponibilidade | `LOW_CAPACITY_REPORTED` | declaração explícita, pausas, latência contextual se pertinente | reduzir complexidade ou pedir confirmação pode diminuir erros | latência isolada não prova fadiga |
| Expectativa que influencia a ação | `EXPECTATION_ACTION_LOOP` | previsão registrada antes da ação, decisão tomada, resultado posterior | a ação mediadora explica parte da associação entre previsão e resultado | chamar de “previsão” algo que a própria ação causou |
| Lembrança seletiva / viés de confirmação | `OUTCOME_REVIEW_REQUIRED` | previsões passadas, erros, acertos, especificidade e timestamp | avaliação prospectiva revela diferença entre confiança subjetiva e calibração | usar somente exemplos memoráveis superestima a capacidade |
| Incerteza ou evidência contraditória | `UNCERTAINTY_ESCALATION` | fontes divergentes, baixa cobertura, mudança de distribuição | abstenção ou pergunta de esclarecimento supera uma previsão forçada | esconder conflitos dentro de uma média |

Um estado só deve ser atribuído quando seus critérios observáveis forem satisfeitos. Se não houver dados adequados, o estado correto é desconhecido/indeterminado — não uma inferência confiante sobre a pessoa.

## 3. Fluxo técnico passo a passo

### Passo 1 — Capturar uma experiência sem reescrevê-la

Registre cada evento no Experience Store com ID estável, `occurred_at`, `recorded_at`, contexto disponível, ator, payload tipado, proveniência e versão do schema. Preserve a observação original. Não converta um pressentimento relatado em fato externo: represente separadamente “a pessoa relatou uma previsão” e “o evento observado aconteceu”.

Exemplo conceitual:

- `experience_type = prediction_reported`
- `prediction_target = meeting_cancelled`
- `prediction_probability = 0.70` (se a pessoa fornecer uma probabilidade)
- `prediction_recorded_at = T0`
- `evidence_available_at = T0`
- `outcome = pending`

A previsão precisa ser registrada **antes** do resultado para impedir que o futuro contamine a evidência disponível no momento da previsão.

### Passo 2 — Construir a trajetória temporal

Agrupe experiências em episódios e ordene por `(occurred_at, id)`. Mantenha separados o horário do evento e o horário de registro. Reconstrua apenas o contexto que estava disponível em T0; dados adicionados depois ficam marcados como posteriores.

Isso evita *temporal leakage*: usar acidentalmente informações do resultado ao avaliar se o sistema poderia prevê-lo.

### Passo 3 — Extrair pistas e características observáveis

A recuperação pode selecionar sinais lexicais, semânticos, temporais, relacionais e de metadados. Uma etapa de extração transforma esses registros em características explícitas: frequência de padrões, ordem dos eventos, novidade, contexto, resultados anteriores e evidência contraditória.

O sistema deve distinguir:
1. **Observado:** consta em fonte identificável.
2. **Relatado:** foi declarado por uma pessoa.
3. **Inferido:** resultado de uma transformação reproduzível ou proposta de modelo.
4. **Desconhecido:** não há evidência suficiente.

Embeddings ou resumos ajudam a recuperar candidatos, mas não substituem os registros originais nem provam uma relação causal.

### Passo 4 — Estimar o estado comportamental com incerteza

Um classificador ou conjunto de regras pode propor um dos estados da tabela, com evidências, confiança, escopo temporal e versão. O resultado deve admitir `UNKNOWN` e `ABSTAIN`. Estado comportamental aqui significa uma condição operacional do raciocínio do sistema — por exemplo, “há conflito entre fontes” — e não um diagnóstico de estado cerebral.

Se sinais biológicos ou emocionais forem utilizados, eles precisam ser fornecidos explicitamente por uma fonte autorizada, com consentimento, finalidade definida e retenção mínima. Não inferir ansiedade, fadiga ou condição clínica como fato a partir de estilo de escrita, silêncio ou latência.

### Passo 5 — Recuperar episódios comparáveis

Busque trajetórias anteriores semelhantes e preserve para cada resultado os componentes do score, a proveniência, a validade temporal e o ciclo de vida. Compare também casos negativos e quase semelhantes, não só exemplos que confirmam a hipótese.

A recuperação híbrida existente é um baseline; seus pesos precisam ser avaliados em dados próprios. Similaridade de conteúdo não equivale a similaridade causal.

### Passo 6 — Consolidar hipóteses via Dreaming

O ciclo offline proposto é:

1. agrupar episódios comparáveis;
2. descrever regularidades observadas;
3. propor uma explicação ou hipótese causal, mantendo-a explicitamente como hipótese;
4. identificar exceções e evidências contraditórias;
5. definir o escopo de validade e as condições em que a regra não deve ser usada;
6. gerar uma `ConsolidationProposal` com claims ligados a `source_ids`;
7. validar e revisar antes de promover conhecimento ativo.

O dreaming atualmente documentado no repositório cobre higiene inicial, como duplicatas textuais e memórias antigas. Descoberta semântica robusta e automatizada de padrões continua sendo trabalho de evolução; este fluxo descreve o alvo arquitetural, não uma capacidade já concluída.

### Passo 7 — Gerar uma previsão prospectiva

O `BehaviorPredictor` pode estimar:

`P(BehaviorID | contexto, evidência, trajetória, histórico)`

Para previsões de resultados, use um alvo definido, janela temporal e conjunto de resultados possíveis. Compare a estimativa com uma taxa-base simples. Registre probabilidade, evidências usadas, versão do modelo/regra, instante da previsão e política de abstenção. Não produza apenas uma narrativa plausível depois do fato.

### Passo 8 — Separar previsão de influência causal

Antes de chamar um padrão de “profecia autorrealizável”, modele explicitamente a cadeia:

`expectativa → decisão/ação → mudança no ambiente → resultado`

Armazene a ação intermediária e compare, quando viável, cenários comparáveis em que a ação foi diferente. Uma associação entre expectativa e resultado, por si só, não identifica causalidade. Use intervenções controladas quando éticas e viáveis; caso contrário, declare as limitações observacionais.

### Passo 9 — Observar o resultado e avaliar a calibração

Quando o desfecho for conhecido, registre-o como uma nova experiência ligada à previsão original, sem sobrescrevê-la. Avalie previsões em lote, incluindo falhas, abstenções e casos sem resultado.

Métricas úteis:
- **Brier score** para probabilidades de eventos binários ou categorias devidamente codificadas;
- **Log loss** quando apropriado e com tratamento seguro de probabilidades extremas;
- **calibração**: entre previsões próximas de 70%, por exemplo, o evento deve ocorrer aproximadamente 70% das vezes numa amostra suficientemente grande;
- **precision/recall** e taxa de falsos positivos para alertas;
- **cobertura**: proporção de casos em que o sistema decidiu prever;
- **comparação com taxa-base** e com uma baseline sem memória;
- **Memory-to-Behavior Gain** para medir se as memórias recuperadas realmente melhoram o resultado.

Nenhuma métrica isolada prova que o mecanismo causal proposto está correto.

### Passo 10 — Atualizar conhecimento sem apagar o passado

Atualize confiança apenas com novos resultados observados e regras de avaliação explícitas. Preserve versões, contradições, proveniência e validade temporal. Use champion/challenger e rollback para impedir que uma hipótese atraente, mas mal calibrada, substitua uma baseline melhor.

## 4. Exemplo completo

Imagine que, em vários episódios, um serviço recebe um aumento gradual de solicitações incompletas antes de atrasos. Um operador relata “pressentir” que haverá atraso.

1. **T0:** o relato e a previsão são registrados com timestamp e probabilidade.
2. **Contexto:** o sistema recupera a sequência anterior de solicitações incompletas, carga e atrasos já observados.
3. **Estado:** propõe `CONTEXT_INTEGRATION`, citando os eventos que sustentam a classificação.
4. **Recuperação:** encontra episódios anteriores, incluindo casos com solicitações incompletas que não terminaram em atraso.
5. **Previsão:** estima a probabilidade de atraso e compara com a taxa-base do serviço.
6. **Ação:** se alguém reduzir a fila ou corrigir os pedidos, registra essa intervenção.
7. **Resultado:** observa se o atraso aconteceu dentro da janela definida.
8. **Avaliação:** calcula calibração e compara os resultados com e sem os sinais recuperados.

Se o atraso não ocorrer, isso não significa automaticamente que o pressentimento era “quase certo”: pode ter sido um falso positivo ou a ação ter mudado o desfecho. O registro da intervenção permite analisar a diferença, mas não resolve sozinho a causalidade.

## 5. Como isso se conecta aos componentes do PreCog

| Componente existente | Papel neste fluxo |
|---|---|
| `Experience` / Experience Store | fonte de verdade para relato, previsão, ação e resultado |
| `Trajectory` | ordenação temporal dos eventos e prevenção de vazamento de informação |
| `RetrievalEvidence` / Retrieval | seleção auditável de episódios e sinais comparáveis |
| `ConsolidationProposal` / ConsolidationEngine | hipótese, evidências, contradições, revisão e promoção controlada |
| Dreaming | processamento offline de padrões candidatos; a descoberta semântica completa ainda é evolução planejada |
| Knowledge graph / `Relation` | relações como `derived_from`, `supports`, `contradicts`, `follows` e `predicts`, sempre com proveniência |
| `BehaviorPredictor` | baseline de distribuição de `BehaviorID`; não é, por si só, um previsor validado de eventos do mundo |
| `outcome_evaluation.py` | avaliação de sucesso, cobertura, confiança e Brier score |
| `continual.py` | comparação champion/challenger e proteção contra regressões |
| PostgreSQL / JSONB / índices | persistência de eventos, metadados, proveniência e resultados, conforme os adapters integrados |
| Markdown + Git projections | inspeção humana e revisão de hipóteses/versionamento |

A implementação atual do PreCog não deve ser descrita como capaz de ler estados biológicos, detectar “gatilhos perfeitos” ou provar precognição. O que ela oferece é uma base para registrar experiências, propor padrões rastreáveis, estimar comportamentos e verificar empiricamente se essas estimativas ajudam.

## 6. Guardrails obrigatórios

- Não apresentar inferência probabilística como certeza ou capacidade paranormal.
- Não avaliar previsões usando dados que só surgiram depois do instante previsto.
- Manter erros, falsos positivos, resultados nulos e previsões não resolvidas no dataset.
- Comparar com taxa-base e baseline; não selecionar apenas acertos memoráveis.
- Não inferir diagnóstico, emoção ou condição fisiológica sem evidência autorizada e adequada.
- Exigir consentimento e minimização de dados pessoais, sobretudo para sinais sensíveis.
- Não permitir que um score de previsão, memória recuperada ou hipótese de dreaming autorize sozinho uma ação externa.
- Preservar proveniência, validade temporal, versões e contradições.
- Preferir abstenção ou pedido de mais contexto quando a evidência for insuficiente.

## 7. Referências para fundamentação

Estas fontes fundamentam os mecanismos gerais descritos; não validam uma alegação de precognição paranormal.

- Clark, A. (2013). *Whatever next? Predictive brains, situated agents, and the future of cognitive science.* Behavioral and Brain Sciences. https://doi.org/10.1017/S0140525X12000477
- Barrett, L. F., & Simmons, W. K. (2015). *Interoceptive predictions in the brain.* Nature Reviews Neuroscience. https://doi.org/10.1038/nrn3950
- Kahneman, D., & Riepe, M. W. (1998). *Aspects of Investor Psychology.* Journal of Portfolio Management. https://doi.org/10.3905/jpm.1998.409643
- Nickerson, R. S. (1998). *Confirmation Bias: A Ubiquitous Phenomenon in Many Guises.* Review of General Psychology. https://doi.org/10.1037/1089-2680.2.2.175
- Roese, N. J., & Vohs, K. D. (2012). *Hindsight Bias.* Perspectives on Psychological Science. https://doi.org/10.1177/1745691612454303
- Merton, R. K. (1948). *The Self-Fulfilling Prophecy.* The Antioch Review. https://doi.org/10.2307/4609267
- Brier, G. W. (1950). *Verification of forecasts expressed in terms of probability.* Monthly Weather Review. https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2
- Tversky, A., & Kahneman, D. (1974). *Judgment under Uncertainty: Heuristics and Biases.* Science. https://doi.org/10.1126/science.185.4157.1124

## 8. Critério de sucesso

A hipótese de engenharia só será sustentada se previsões registradas antes dos resultados forem mais úteis que uma taxa-base, permanecerem calibradas em dados novos, incluírem erros e casos negativos, e demonstrarem ganho mensurável com evidências recuperadas. A meta é **precisão comportamental verificável com incerteza explícita**, não transformar a sensação de certeza em evidência.
