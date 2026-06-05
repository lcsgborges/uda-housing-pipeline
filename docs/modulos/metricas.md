# Métricas e Conjuntura

## Visão Bruta

`GET /api/metrics` retorna todas as métricas persistidas, com filtros opcionais:

```http
GET /api/metrics?empresa=MRV&ano=2025&trimestre=3&metrica=vendas_liquidas
```

Essa visão é auditável e não deduplica resultados. Ela expõe o que foi persistido em `metrics` após validação Pydantic e normalização por catálogo.

## Camada de Conjuntura

`GET /api/conjuntura` retorna uma visão final para consumo analítico:

```http
GET /api/conjuntura?empresa=MRV&ano=2025&trimestre=3
```

Ela deduplica métricas por nome canônico e escolhe a melhor evidência usando:

- valor presente;
- confiança;
- página informada;
- trecho-fonte;
- presença no catálogo canônico.

Internamente, a seleção usa `_metric_quality_score()` e `_metric_rank()` em `app/modules/metrics/service.py`. O score é limitado entre `0` e `100` e considera confiança, valor, página, trecho e aderência ao catálogo.

## Resposta

Cada item traz:

- `nome`
- `categoria`
- `valor`
- `unidade`
- `fonte`
- `confianca`
- `qualidade`

Exemplo:

```json
{
  "nome": "vendas_liquidas",
  "categoria": "operacional",
  "valor": 123400000.0,
  "unidade": "R$",
  "confianca": 0.99,
  "qualidade": {
    "camada": "gold",
    "nivel": "alta",
    "score": 100
  }
}
```

## Vocabulário Controlado

O arquivo `app/modules/metrics/catalog.py` é o ponto central para:

- nomes canônicos;
- aliases;
- categoria;
- unidade padrão;
- moeda padrão;
- prioridade de ordenação.

Ao adicionar uma métrica recorrente, atualize o catálogo e os testes.

## Filtros

`MetricService.list_all()` resolve `empresa` por nome ou ticker, ignorando acentos e caixa. O filtro `metrica` passa por `canonical_metric_name()`, então aliases conhecidos apontam para o mesmo nome canônico.

## Valores e Unidades

Durante a persistência, `_normalize_unit_and_currency()` preenche unidade e moeda usando defaults do catálogo. Quando a LLM devolve `unit` como `BRL` ou `USD`, esse valor é tratado como moeda e a unidade volta ao default do catálogo quando disponível.
