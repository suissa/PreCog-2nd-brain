# PreCog-2nd-Brain

**PreCog é um substrato cognitivo persistente, temporal e orientado por proveniência para sistemas agentic.** Transforma experiências observadas em memórias recuperáveis e conhecimento validado, para que experiências consolidadas ajudem a inferir padrões e, futuramente, antecipar comportamentos e selecionar próximas ações.

A ideia não é apenas armazenar conversas, resumir textos ou adicionar um banco vetorial a um agente. É manter uma trilha verificável entre **o que aconteceu, o que foi inferido, qual evidência sustenta a inferência, quando ela era válida e como poderá influenciar um comportamento futuro**.

> **Lei fundamental:** experiência é evidência; memória e conhecimento são estados derivados. Um resumo, embedding, grafo ou resposta de modelo nunca substitui a experiência original como fonte de verdade.

- **PreCog** é a camada cognitiva persistente.
- **XP.2Flow** é a camada declarativa que pode orquestrar transformações entre experiência, consolidação, conhecimento, capacidade e comportamento. Consulte o [contrato XP.2Flow](docs/XP.2Flow.md), que separa o protocolo conceitual do runtime ainda a implementar.
- O contrato normativo está em [PRE-CORD.md](PRE-CORD.md); visão técnica em [ARCHITECTURE.md](ARCHITECTURE.md), [TECHNOLOGY.md](TECHNOLOGY.md) e [ROADMAP.md](ROADMAP.md).
- Para a modelagem de pressentimentos como inferência comportamental verificável, consulte [Precognição como inferência comportamental](docs/PRECOGNITION-BEHAVIORAL-STATES.md): estados propostos, fluxo técnico, avaliação prospectiva e guardrails científicos.

## 1. A evolução: COG + dreaming + knowledge graph

PreCog parte de mecanismos conhecidos em arquiteturas cognitivas e sistemas de memória para agentes — memória episódica/semântica, recuperação, reflexão, consolidação offline e relações entre fatos — e os combina sob contratos explícitos de proveniência, temporalidade, validação e evolução.

### COG / AI Second Brain

A inspiração de *cognitive architecture* e *AI second brain* é separar a experiência bruta das representações que ajudam a raciocinar. Em vez de depender apenas da janela de contexto de um LLM, o sistema conserva registros persistentes, recupera o subconjunto relevante e organiza conhecimento inspecionável por pessoas.

PreCog reutiliza essa separação entre memória, recuperação e reflexão, tornando explícitos os contratos de domínio: entidades tipadas, proveniência, validade temporal, ciclo de vida, idempotência, preservação de conflitos e reconstrução de estados derivados. Markdown e Git são projeções legíveis e auditáveis, não substitutos do armazenamento canônico.

### Dreaming

*Dreaming* é o trabalho offline sobre experiências e memórias acumuladas, separado do caminho síncrono de atendimento. Pode deduplicar, encontrar informação envelhecida, relacionar experiências, propor generalizações e preparar candidatos para revisão sem bloquear a execução cotidiana.

O módulo [src/precog/dreaming.py](src/precog/dreaming.py) implementa uma primeira etapa determinística de higiene: normaliza texto com remoção de espaços externos e conversão para minúsculas, identifica duplicatas textuais e memórias ativas antigas e as arquiva com nova versão. O relatório informa itens examinados, duplicados, obsoletos e arquivados. **É uma implementação inicial de dreaming, não um mecanismo completo de descoberta semântica de padrões.** RCA, reflexão, generalização e alterações propostas pertencem ao fluxo de consolidação e podem usar adapters de modelo.

### Knowledge graph

Um grafo de conhecimento representa objetos como nós e afirmações tipadas como arestas. Permite navegar entre experiências, consequências, evidências, generalizações, contradições e sucessões temporais.

PreCog define relações como **derived_from**, **caused_by**, **supports**, **contradicts**, **generalizes**, **specializes**, **supersedes**, **follows**, **related_to**, **applies_to** e **predicts**. Cada relação pode carregar confiança, tempo e proveniência. O grafo organiza relações entre evidências; não é uma autoridade independente delas.

### O que PreCog acrescenta

1. **Provenance-first:** toda memória e conhecimento derivados apontam para experiências que os sustentam.
2. **Temporalidade explícita:** diferencia quando algo aconteceu (occurred_at), quando foi registrado (recorded_at) e o intervalo em que uma afirmação é válida.
3. **Consolidação como proposta:** observações, RCA, generalizações, contradições e mudanças candidatas são reunidas com evidências e passam por validação antes de se tornarem estado ativo.
4. **Conflito preservado:** afirmações incompatíveis podem coexistir com suas fontes e períodos de validade; a história não é apagada silenciosamente para forçar uma única versão.
5. **Recuperação como seleção de evidência:** combina sinais lexicais, semânticos, temporais, relacionais e de metadados em vez de despejar todo o armazenamento no prompt.
6. **Estado derivado reconstruível:** embeddings, índices, projeções Markdown e futuras projeções de grafo podem ser refeitos a partir de dados canônicos e da versão da derivação.
7. **Previsão ligada ao comportamento:** experiências podem registrar intent_id, behavior_id, ação e resultado, preparando a estimativa de P(BehaviorID | contexto, evidência, trajetória).
8. **Evolução com guardrails:** avaliação offline, métricas de resultado, champion/challenger e rollback separam experimentação de promoção.

Esses pontos são objetivos arquiteturais; o status de cada mecanismo é discriminado adiante para não confundir contratos e protótipos com capacidades ainda planejadas.

## 2. O ciclo cognitivo

    Experiência observada
            |
            v
    Experience Store — append-only, identidade e proveniência
            |
            v
    Trajetória — sequência temporal e contexto
            |
            v
    Recuperação — candidatos lexicais + semânticos + temporais + relacionais
            |
            v
    Consolidação / Dreaming
      observações -> RCA/reflexão -> abstração -> generalização
            |
            v
    Proposta com evidências, confiança, benefício e validações
            |
            +---- rejeitada ----> mantém evidência; não ativa a proposta
            |
            v aprovada
    Memória versionada + Conhecimento versionado + relações
            |
            v
    Projeções legíveis / índices reconstruíveis
            |
            v
    Contexto futuro -> previsão de BehaviorID -> avaliação -> próxima ação
            |
            v
    Nova experiência (fecha o ciclo)

Forma resumida:

**Experience → Consolidation → Knowledge → Capability → Behavior → Experience**

Memória e recuperação atravessam o ciclo: são representações intermediárias que tornam a experiência utilizável sem substituir sua fonte original. Previsão de comportamento é uma camada posterior ao armazenamento e à recuperação, não sinônimo de memória.

## 3. Conceitos e modelo de dados

Os contratos de domínio estão principalmente em [src/precog/models.py](src/precog/models.py).

| Conceito | Significado |
|---|---|
| **Experience** | Registro de algo observado ou executado: ID, trajetória, tempos ocorrido/registrado, ator, tipo de evento, payload, proveniência e versão do schema. Pode registrar intenção, BehaviorID, ação e resultado. |
| **Trajectory** | Sequência ordenada de experiências que compõem uma execução ou episódio. A reconstrução diagnostica IDs duplicados, experiências ausentes e reordenação temporal. |
| **Memory** | Representação derivada com tipo, conteúdo, fontes, confiança, saliência, validade temporal, proveniência, metadados, versão e ciclo de vida. |
| **Knowledge** | Afirmação generalizada com escopo, evidências, confiança, status, versão, validade temporal e proveniência. |
| **Relation** | Aresta tipada entre objetos, com confiança, intervalo temporal e fontes da derivação. |
| **Behavior** | Contrato comportamental com intenção, pré-condições, contexto, ações, resultado esperado, evidências, confiança, estado e versão. |
| **RetrievalEvidence** | Resultado recuperado com identidade, score geral e componentes, proveniência, ciclo de vida e tipo de fonte. Não concede autoridade para executar ações. |
| **ConsolidationProposal** | Hipótese auditável com evidências, observações, RCA, generalização, mudanças candidatas, contradições, confiança, benefício esperado e requisitos de validação. |
| **EmbeddingRecord** | Índice vetorial reconstruível vinculado à versão e ao hash da memória, modelo, versão do provider e dimensões. |

### Tipos e ciclo de vida de memória

Os tipos previstos são **episodic**, **semantic**, **entity**, **procedural** e **observational**. O tipo descreve a forma da informação; não elimina a obrigação de manter as fontes.

O ciclo de vida definido é:

**captured → candidate → validated → active → dormant → superseded → archived**

As transições são controladas. Arquivar não significa apagar a experiência. Mudanças em uma memória existente avançam sua versão; o store de referência mantém histórico de versões.

### Proveniência

A estrutura Provenance contém source_ids, derivation e schema_version. Uma inferência precisa responder: **quais fontes a sustentam e por qual transformação foi criada?** Claims individuais de propostas de consolidação também apontam para fontes. Fontes desconhecidas ou claims sem evidência devem ser rejeitados antes da materialização canônica.

## 4. Consolidação e inferência de padrões

Consolidação é a passagem de eventos particulares para representações úteis em experiências futuras. A inferência não deve ser confundida com texto gerado por um modelo: a hipótese precisa estar ligada às evidências e sujeita a validação.

O [ConsolidationEngine](src/precog/consolidation.py) define este fluxo:

1. Selecionar experiências de origem e o estado derivado relevante.
2. Solicitar a um adapter uma proposta estruturada.
3. Construir claims de evidência e observação, análise de causa-raiz (RCA), generalização, alterações candidatas e possíveis contradições.
4. Validar estrutura, confiança, fontes e requisitos de evidência.
5. Registrar decisão explícita: aceitar ou rejeitar.
6. Somente após aceitação, materializar memória e conhecimento versionados; rejeição não modifica o estado canônico.
7. Manter revisão idempotente e impedir que uma decisão contraditória seja silenciosamente aplicada à mesma proposta.

O adapter determinístico serve como baseline reproduzível e para testes. Adapters de modelos podem produzir extração, sumarização, reflexão e RCA, mas uma falha do provider deve ocorrer antes de qualquer mutação canônica. O modelo sugere; as regras determinísticas verificam invariantes e governam a transição.

### Como surgem padrões

Um padrão útil pode ser recorrência de eventos, associação entre contexto e resultado, causa provável, exceção ou regra aplicável a uma classe de trajetórias. A sequência pretendida é:

- **Observação:** resumir o que os registros mostram.
- **Comparação:** relacionar episódios semelhantes e diferentes.
- **RCA/reflexão:** propor explicações para resultados e falhas.
- **Abstração:** separar características essenciais de detalhes incidentais.
- **Generalização:** propor regra com escopo e limites explícitos.
- **Contradição:** localizar evidências incompatíveis e preservar seus contextos.
- **Validação:** exigir evidência, consistência temporal e testes aplicáveis.
- **Ativação controlada:** promover o resultado somente depois da revisão exigida.

O código atual cobre a estrutura de propostas, validação de evidência, decisão de revisão e materialização protegida. Descoberta semântica robusta de padrões entre grandes conjuntos de trajetórias e dreaming agendado que execute o ciclo completo ainda são evolução planejada.

## 5. Recuperação híbrida: buscar evidência, não despejar memória

O caminho de recuperação está em [src/precog/retrieval.py](src/precog/retrieval.py) e [src/precog/retrieval_repository.py](src/precog/retrieval_repository.py). O contrato combina sinais separados para que possam ser avaliados individualmente.

- **Lexical:** tokenização determinística por expressão regular e sobreposição de tokens normalizada.
- **Semantic:** similaridade de cosseno entre embeddings compatíveis; vetores e índices são derivados.
- **Temporal:** compatibilidade com o instante consultado e os intervalos valid_from/valid_to.
- **Relation:** sinal de relações associadas ao objeto.
- **Metadata:** filtros de ciclo de vida e, quando disponível, tenant, ator ou outros metadados.
- **Reranking:** adapter opcional, isolado do contrato canônico.

A fusão de baseline é determinística:

    score = 0.45 * lexical
          + 0.30 * semantic
          + 0.15 * temporal
          + 0.10 * relation

O score é limitado a [0, 1] e empates são ordenados por ID para resultados reproduzíveis. Os pesos são uma configuração inicial, não uma verdade universal; precisam ser avaliados com datasets e métricas de precisão/recall. O adapter PostgreSQL atual faz uma projeção lexical/temporal/relacional e não deve ser confundido com um pipeline de embeddings completo em produção.

O pacote retornado conserva ID, score e componentes, proveniência, estado e validade. A camada consumidora decide como incorporar a evidência ao contexto; um item recuperado não é instrução executável nem autorização.

## 6. Relações e grafo temporal

As relações conectam experiências, memórias e conhecimento. A implementação em [src/precog/relations.py](src/precog/relations.py) permite travessia limitada por profundidade e tipos de relação, devolvendo caminhos com arestas e proveniências.

Relações selecionadas — como derived_from, caused_by, generalizes, specializes, supersedes e follows — têm política de aciclicidade para impedir ciclos semânticos inválidos. Relações como supports podem formar ciclos quando a semântica permite. A remoção de relação é auditada no store de referência; endpoints e fontes devem existir.

O grafo canônico inicial é relacional. Um banco de grafo dedicado (por exemplo, Neo4j ou FalkorDB) e projeções como Graphiti são **opcionais**: só devem ser adicionados se benchmarks e requisitos de consulta justificarem a complexidade. Não é necessário duplicar agora a fonte de verdade em outro banco.

## 7. Predição e evolução comportamental

A direção PreCog é inferir qual comportamento é provável dado o contexto, trajetória e evidência recuperada:

**P(BehaviorID | contexto, evidência recuperada, trajetória, histórico)**

O [BehaviorPredictor](src/precog/prediction.py) é hoje uma baseline determinística: conta ocorrências por BehaviorID e atribui peso adicional às experiências ligadas à proveniência da recuperação; normaliza os scores para probabilidades relativas e devolve IDs de evidência. Não é ainda um modelo estatístico treinado nem prova de causalidade.

O [JevRankerAdapter](src/precog/ranker.py) define uma fronteira para reranking externo. [outcome_evaluation.py](src/precog/outcome_evaluation.py) mede acurácia de comportamento, taxa de sucesso, confiança, Brier score e cobertura de evidência. [continual.py](src/precog/continual.py) fornece decisões champion/challenger, guardrails contra regressão e rollback; essas decisões não implantam um modelo automaticamente.

A métrica experimental **Memory-to-Behavior Gain** compara o resultado downstream com e sem o conjunto de memórias selecionado. Ela deve ser medida em avaliações controladas, não presumida a partir de um score de recuperação.

## 8. Persistência, bancos locais e projeções

O princípio é reutilizar a infraestrutura existente e manter uma única fonte de verdade canônica.

### PostgreSQL — persistência canônica planejada para v1 e adapter existente

O baseline definido em [TECHNOLOGY.md](TECHNOLOGY.md) é PostgreSQL, usando:

- tabelas relacionais para identidade, entidades, ciclo de vida, relações e timestamps;
- **JSONB** para payloads extensíveis, proveniência e metadados;
- transações para operações de persistência;
- **PostgreSQL Full-Text Search** como busca lexical inicial;
- **pgvector** para índice semântico vetorial dentro do mesmo PostgreSQL;
- migrações versionadas em [sql/](sql/).

O adapter [src/precog/postgres.py](src/precog/postgres.py) implementa operações para experiência, trajetória, memória, conhecimento, relações e candidatos de recuperação. As migrações incluem constraints canônicas, versionamento de memória e estrutura de embeddings. A presença de schema e adapter não significa, por si só, que um servidor PostgreSQL esteja provisionado ou que todas as rotas estejam validadas contra uma instância de produção.

### InMemoryStore — execução local e testes

[src/precog/store.py](src/precog/store.py) oferece store de referência em memória para testes determinísticos e execução local sem infraestrutura externa. É útil para validar invariantes, transições de estado, proveniência, temporalidade e grafo. **Não é armazenamento durável**: o estado se perde ao encerrar o processo.

### Filesystem + Markdown + Git

[src/precog/projection.py](src/precog/projection.py) gera projeções Markdown determinísticas de memórias e conhecimentos, com metadados, versão, conteúdo e fontes. IDs são validados antes de virar segmentos de caminho. Git pode versionar e revisar essas projeções, oferecendo diffs legíveis e histórico humano.

As projeções são reconstruíveis; editar um arquivo projetado não altera automaticamente o estado canônico.

### O que não é requisito inicial

- **Neo4j/FalkorDB/Graphiti:** possível projeção de grafo futura, condicionada a necessidade medida.
- **Serviço vetorial separado:** não é fonte canônica; pgvector mantém o índice junto ao PostgreSQL.
- **Broker assíncrono, como NATS:** opção futura se o volume justificar consolidação assíncrona distribuída.
- **Object storage:** opção para artefatos brutos grandes.
- **LLM ou embedding provider específico:** substituível por adapter; nenhum fornecedor deve definir o schema de domínio.

### Linguagem e maturidade do código

O baseline de tecnologia aponta TypeScript como linguagem primária planejada. **A implementação de referência atualmente presente em src/precog é Python**, com testes pytest, typing/mypy e CI. A documentação diferencia essa realidade do baseline arquitetural para não sugerir que já existe uma implementação TypeScript completa.

## 9. Adapters e falhas isoladas

Operações dependentes de modelo são abstraídas por protocolos: extração, sumarização, reflexão, RCA, embeddings, reranking e previsão. [src/precog/adapters.py](src/precog/adapters.py) inclui adapters de modelo com endpoint HTTP compatível com OpenAI, política de retry e erros tipados para falhas HTTP, timeout ou respostas inválidas. Configuração de endpoint, modelo e credenciais pertence ao runtime, não às entidades canônicas.

Identidade, proveniência, autorização, ciclo de vida e validação temporal devem permanecer determinísticos. Uma falha de modelo, embedding, reranker ou projeção não pode corromper a experiência original. Índices e projeções são reconstruíveis.

## 10. Algoritmos e estruturas de dados

| Área | Algoritmo/estrutura atual | Objetivo |
|---|---|---|
| Identidade e proveniência | IDs estáveis, referências por ID e hashes SHA-256 de conteúdo/versão | Idempotência e verificação de frescor dos derivados |
| Store em memória | Dicionários indexados por ID, tuplas imutáveis e histórico de versões | Acesso determinístico e transições auditáveis |
| Trajetórias | Ordenação por (occurred_at, id); diagnóstico de duplicatas e lacunas | Reconstruir sequência temporal |
| Recuperação lexical | Tokenização por regex, contagem de tokens e sobreposição normalizada | Baseline lexical local reproduzível |
| Recuperação semântica | Embeddings e similaridade de cosseno | Encontrar conteúdo semanticamente próximo |
| Fusão híbrida | Soma ponderada de sinais e desempate por ID | Combinar evidências de forma reproduzível |
| Grafo | Relações como adjacência, busca em largura (BFS) com profundidade limitada e verificação de ciclo por alcançabilidade | Explorar relações com custo e escopo limitados |
| Deduplicação inicial | Chave de conteúdo normalizada por trim e minúsculas | Detectar duplicatas textuais simples |
| Validação de consolidação | Claims tipados, fontes verificadas, decisões aceitas/rejeitadas e materialização idempotente | Impedir promoção silenciosa de hipóteses |
| Avaliação de confiança | Brier score, acurácia, taxa de sucesso e cobertura de evidência | Avaliar previsões com resultados observados |
| Projeção Markdown | Serialização JSON determinística, paths seguros e arquivos reconstruíveis | Auditoria humana e revisão em Git |

Os algoritmos simples são intencionais para formar uma baseline transparente. BM25 completo, busca semântica em escala, descoberta avançada de padrões, ranking aprendido e avaliação em benchmarks devem ser incorporados por etapas e comparados com a baseline.

## 11. Segurança, consistência e invariantes

- Experiências comprometidas são append-only; correções entram como novos registros, não como sobrescrita silenciosa.
- Memórias e conhecimentos derivados preservam IDs de origem e versão da derivação.
- Intervalos temporais inválidos devem ser rejeitados.
- Duplicatas de ingestão com mesmo ID e conteúdo são idempotentes; mesmo ID com conteúdo diferente é conflito.
- Memórias arquivadas ficam fora da recuperação ativa por padrão.
- Contradições são representadas explicitamente, com proveniência e validade temporal.
- Falhas de providers não podem promover dados parciais para estado canônico.
- Embeddings têm metadados de modelo, versão, dimensões, versão/hash da fonte e timestamp no contrato.
- Dados pessoais e segredos precisam de classificação, redaction e política de retenção antes de entrar em embeddings, logs, traces ou projeções irrestritas.
- Recuperar uma memória não concede autorização para executar a ação descrita nela.

## 12. Testes e avaliação

A suíte em [tests/](tests/) cobre modelos, contratos, trajetórias, temporalidade, recuperação, embeddings, adapters, consolidação, relações, projeções, avaliação de resultados, promoção e rollback. A CI executa testes, checagem estática de tipos e validação de rastreabilidade.

Além de testes unitários, a evolução deve medir precisão/recall e ranking da recuperação, completude de proveniência, consistência temporal, tratamento de contradições, cobertura das experiências pela memória, utilidade comportamental, calibração (Brier score), Memory-to-Behavior Gain, custo e latência.

Datasets propostos incluem LOCOMO e LongMemEval, complementados por cenários próprios de trajetórias, contradições e evidência temporal. Um mecanismo só deve substituir a baseline quando a avaliação demonstrar ganho sem violar guardrails.

## 13. Base conceitual e referências

PreCog combina ideias documentadas em pesquisas e projetos de memória para agentes, sem alegar ter inventado cada mecanismo individualmente:

- **CoALA** — separação de memória, raciocínio e ação em arquiteturas cognitivas.
- **Generative Agents** — fluxo de memórias, recuperação e reflexão.
- **Reflexion** — feedback verbal e melhoria iterativa.
- **MemGPT/Letta** — memória externa hierárquica e operações sobre memória.
- **HippoRAG / HippoRAG 2** — recuperação associativa assistida por grafos.
- **A-MEM** — unidades de memória e relações dinâmicas.
- **Graphiti/Zep** — relações temporais e recuperação híbrida.
- **Mem0** — extração e recuperação estruturada de memória.
- **WikiSkill** — progressão de conhecimento organizado para capacidades.
- **APEX-MEM** e surveys recentes — persistência append-only, temporalidade, consolidação e resolução de conflitos na recuperação.

Detalhes bibliográficos estão em [REFERENCES.md](REFERENCES.md). A fronteira experimental do PreCog é a integração desses mecanismos sob proveniência unificada, memória orientada a trajetórias, recuperação ligada a BehaviorID, avaliação Memory-to-Behavior Gain, previsão de PreCog e evolução declarativa via XP.2Flow.

## 14. Estado atual e próximos passos

O repositório é uma implementação incremental e *specification-first*, não um sistema autônomo completo já operando em produção.

**Já representado por código e testes:** entidades e invariantes; store em memória; adapter PostgreSQL e migrações; reconstrução de trajetórias; recuperação lexical/híbrida e contrato de recuperação semântica; registro de embeddings e adapters; relações e travessia limitada; propostas de consolidação com evidência e revisão; higiene inicial de dreaming; projeções Markdown; baseline de previsão de BehaviorID; avaliação de resultados e decisões de promoção/rollback.

**Ainda exige integração, validação operacional ou evolução:** provisionamento e testes ponta a ponta em PostgreSQL real; pipeline semântico completo com pgvector e providers concretos; scheduler de dreaming e descoberta semântica de padrões em escala; resolução temporal de conflitos mais avançada; benchmarks reprodutíveis; previsão calibrada em dados reais; integração de ponta a ponta com XP.2Flow, Jev/BestNextAction e evolução segura de skills/código.

O princípio das próximas etapas permanece: **inferir padrões a partir de experiências consolidadas, preservar as evidências que sustentam cada inferência e só transformar hipóteses em memória/conhecimento ativos quando os critérios de validação forem satisfeitos.**
