import pytest

from app.modules.companies.router import delete_company


class StubCompanyService:
    def __init__(self):
        """Inicializa o stub sem empresa removida."""
        self.deleted_company_id = None

    async def delete(self, company_id: int):
        """Registra o ID recebido pelo endpoint de remoção."""
        self.deleted_company_id = company_id


@pytest.mark.asyncio
async def test_delete_company_returns_204_response():
    """Garante que o router de delete devolve resposta 204."""
    service = StubCompanyService()

    response = await delete_company(123, service)

    assert response.status_code == 204
