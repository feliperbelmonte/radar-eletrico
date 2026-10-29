"""Testes offline do radar (python -m unittest discover -s tests)."""
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import radar  # noqa: E402

AGORA = datetime.fromisoformat("2026-10-29T06:17:00-03:00")
FIXTURE = RAIZ / "tests" / "fixtures" / "api_exemplo.json"


def item(objeto, encerra="2026-11-20T10:00:00", **extra):
    base = {
        "numeroControlePNCP": "x", "anoCompra": 2026, "sequencialCompra": 7, "modalidadeId": 8,
        "modalidadeNome": "Dispensa", "objetoCompra": objeto, "valorTotalEstimado": 50000.0,
        "dataEncerramentoProposta": encerra, "dataPublicacaoPncp": "2026-10-01T10:00:00",
        "orgaoEntidade": {"cnpj": "12.345.678/0001-90", "razaoSocial": "MUNICIPIO X"},
        "unidadeOrgao": {"ufSigla": "PR", "municipioNome": "Curitiba"},
    }
    base.update(extra)
    return base


class TestTexto(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(radar.normalizar("  Instalações  ELÉTRICAS / NR-10 "), "instalacoes eletricas nr 10")

    def test_prefixo_e_palavra_inteira(self):
        r = radar.compilar(["fotovolta*", "obra"])
        self.assertTrue(r.search("sistema fotovoltaico"))
        self.assertTrue(r.search("execucao da obra"))
        self.assertFalse(r.search("e obrigatorio"))

    def test_potencias(self):
        self.assertEqual(radar.potencias("usina de 75 kwp"), ([75.0], []))
        self.assertEqual(radar.potencias("usina de 1,5 mwp"), ([1500.0], []))
        self.assertEqual(radar.potencias("consumo de 500 kwh por mes"), ([], []))
        self.assertEqual(radar.potencias("trafo 1.000 kva e 0,5 mva"), ([], [1000.0, 500.0]))


class TestClassificar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.regras = radar.carregar_regras(RAIZ / "config.toml")

    def c(self, *a, **k):
        return radar.classificar(item(*a, **k), self.regras, AGORA)

    def test_solar_pequeno_entra_no_grupo_2(self):
        r, motivo = self.c("Instalação de sistema fotovoltaico de 30 kWp na UBS")
        self.assertEqual(motivo, "ok")
        self.assertEqual((r["grupo"], r["escopo"]), (2, "solar"))
        self.assertTrue(r["dentroLimiteDispensa"])
        self.assertEqual(r["link"], "https://pncp.gov.br/app/editais/12345678000190/2026/7")

    def test_solar_grande_sai(self):
        self.assertEqual(self.c("Usina fotovoltaica de 300 kWp")[1], "potencia_acima")

    def test_subestacao_acima_de_1mva_sai(self):
        self.assertEqual(self.c("Projeto de subestação de 1.500 kVA")[1], "potencia_acima")

    def test_projeto_com_obra_vira_atencao(self):
        r, _ = self.c("Elaboração de projeto elétrico e execução da obra")
        self.assertEqual((r["grupo"], r["status"]), (1, "atencao"))
        self.assertIn("ATENÇÃO", r["objeto"])

    def test_compra_de_material_sai(self):
        self.assertEqual(self.c("Aquisição de materiais elétricos e quadros de distribuição")[1], "termo_excluido")
        self.assertEqual(self.c("Fornecimento de quadros de distribuição")[1], "compra_de_material")

    def test_prazo_vencido_sai(self):
        self.assertEqual(self.c("Projeto elétrico", encerra="2026-10-28T10:00:00")[1], "prazo_vencido")

    def test_sem_prazo_sai(self):
        self.assertEqual(self.c("Projeto elétrico", encerra=None)[1], "sem_prazo")

    def test_locacao_sai(self):
        self.assertEqual(self.c("Locação de usina fotovoltaica para créditos")[1], "termo_excluido")

    def test_urgente_tem_prioridade(self):
        r, _ = self.c("Projeto elétrico e execução da obra", encerra="2026-11-02T10:00:00")
        self.assertEqual(r["status"], "urgente")

    def test_novo(self):
        r, _ = self.c("Laudo de SPDA", dataPublicacaoPncp="2026-10-28T10:00:00")
        self.assertEqual(r["status"], "novo")

    def test_residencial_precisa_falar_de_eletrica(self):
        self.assertEqual(self.c("Construção de 40 casas populares")[1], "fora_do_escopo")
        r, _ = self.c("Instalações elétricas de 40 casas populares")
        self.assertEqual(r["escopo"], "residencial")


class TestPipeline(unittest.TestCase):
    def test_fixture_ponta_a_ponta(self):
        with tempfile.TemporaryDirectory() as tmp:
            saida = Path(tmp)
            res = radar.executar(saida, RAIZ / "config.toml", FIXTURE, AGORA, log=lambda m: None)
            self.assertEqual(res["analisados"], 13)  # 14 linhas, 1 duplicada
            self.assertEqual(res["relevantes"], 7)
            painel = (saida / "painel.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(1)</script>", painel)
            self.assertEqual(painel.count(radar.MARCA_INI), 1)
            self.assertIn("const RUN_NOTE =", painel)
            notif = (saida / "notificacao.txt").read_text(encoding="utf-8")
            self.assertTrue(notif.startswith("Varredura de 29/10, 06h17: 7 editais relevantes"))
            json.loads((saida / "licitacoes.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
