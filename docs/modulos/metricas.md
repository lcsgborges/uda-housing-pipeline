# Métricas e Conjuntura

## Visão Bruta

`GET /api/metrics` retorna todas as métricas persistidas, com filtros opcionais:

```http
GET /api/metrics?empresa=MRV&ano=2025&trimestre=3&metrica=vendas_liquidas
```

Essa visão é auditável e não deduplica resultados.

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
