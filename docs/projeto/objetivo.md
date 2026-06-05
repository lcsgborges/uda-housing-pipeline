# Objetivo e Escopo

## Objetivo

O objetivo do projeto é transformar documentos não estruturados do mercado habitacional em dados relacionais rastreáveis, com foco inicial em PDFs de resultados, prévias operacionais, relatórios de sustentabilidade e boletins de conjuntura.

O sistema foi desenhado para responder perguntas como:

- Quais métricas uma empresa divulgou em um trimestre?
- Qual documento e trecho sustentam cada métrica?
- Que fatos documentais úteis aparecem sem valor numérico explícito?
- Quais métricas podem ser usadas em uma visão consolidada de conjuntura?
- O documento já foi processado ou é duplicado?
- O documento deve ser extraído, ignorado ou marcado como dependente de OCR?

## Problema Resolvido

Relatórios de RI e boletins costumam ter dados relevantes em tabelas, texto corrido e layouts variados. Isso dificulta análise comparável entre empresas e períodos.

O pipeline reduz esse problema com:

- ingestão automatizada;
- idempotência por hash;
- parsing de PDF;
- classificação pré-extração;
- seleção semântica de contexto;
- extração por LLM com schema rígido;
- persistência separada de métricas e insights;
- normalização por catálogo canônico;
- linhagem por documento, página e trecho.

## Fora do Escopo Atual

- Crawling altamente específico para todo site de RI.
- Extração visual avançada de tabelas por coordenadas.
- Embeddings vetoriais para recuperação semântica.
- Dashboard BI nativo.
- Treinamento de modelo próprio.

Esses pontos podem ser adicionados depois, sem quebrar a arquitetura atual.

## Critérios de Qualidade

Uma métrica só deve ser persistida se passar pelo contrato Pydantic e tiver valor numérico explícito. Informações úteis sem valor numérico entram como insights. Para ser útil na camada de conjuntura, uma métrica deve ter evidência rastreável: documento, página, trecho e confiança.
